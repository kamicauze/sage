"""
Whisper LoRA Fine-tuning for Kenyan Phonetics / Sheng STT

Fine-tunes Whisper (small or medium) with LoRA adapters to improve
syllable-level accuracy on Kenyan-accented speech. The model learns
the phonetic patterns; post-processing handles Sheng lexicon lookup.

Designed for NVIDIA 4070 Ti (12GB VRAM).
Exports to CTranslate2 format for faster-whisper deployment on Jetson.

Usage:
    python brain/voice/training/finetune_stt.py
    python brain/voice/training/finetune_stt.py --model whisper-medium --epochs 5
"""

import os
import sys
import json
import argparse
import logging
import inspect

# Ensure workspace root is importable when run via apps/... path.
from pathlib import Path

_probe = Path(__file__).resolve().parent
for _parent in [_probe, *_probe.parents]:
    if (_parent / "sage.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from brain.voice.paths import get_training_artifacts_dir, get_training_data_dir

logging.basicConfig(level=logging.INFO, format="[STT-Train] %(asctime)s - %(message)s")
logger = logging.getLogger("STT-Train")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(str(get_training_data_dir(__file__)), "stt_dataset")
CHECKPOINT_ROOT = os.path.join(str(get_training_artifacts_dir(__file__)), "checkpoints")


def train(args):
    """Run Whisper LoRA fine-tuning."""
    import torch
    import evaluate
    from datasets import Dataset, Audio
    from transformers import (
        WhisperForConditionalGeneration,
        WhisperProcessor,
        Seq2SeqTrainingArguments,
        Seq2SeqTrainer,
    )
    from peft import LoraConfig, get_peft_model
    from functools import partial

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")
    if device == "cuda":
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")

    # Model selection
    model_name = f"openai/{args.model}"
    logger.info(f"Base model: {model_name}")

    # Load processor
    processor = WhisperProcessor.from_pretrained(model_name)
    processor.tokenizer.set_prefix_tokens(language="sw", task="transcribe")

    # Load model
    # transformers is transitioning from `torch_dtype` to `dtype`.
    try:
        model = WhisperForConditionalGeneration.from_pretrained(
            model_name,
            dtype=torch.float16,
        )
    except TypeError as exc:
        if "dtype" not in str(exc):
            raise
        model = WhisperForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
        )
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    # Apply LoRA
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    # Required when combining LoRA with gradient checkpointing on frozen bases.
    # Without this, checkpointed activations can detach and loss.backward() fails.
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.config.use_cache = False
    model.print_trainable_parameters()

    # Load datasets
    train_path = os.path.join(args.data_dir, "train.jsonl")
    val_path = os.path.join(args.data_dir, "val.jsonl")

    if not os.path.exists(train_path):
        logger.error(f"Training data not found at {train_path}")
        logger.error("Run prepare_stt_data.py first.")
        sys.exit(1)

    def load_jsonl(path):
        entries = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line.strip()))
        return entries

    train_entries = load_jsonl(train_path)
    val_entries = load_jsonl(val_path) if os.path.exists(val_path) else []

    logger.info(f"Train samples: {len(train_entries)}, Val samples: {len(val_entries)}")

    # Create HuggingFace datasets
    train_ds = Dataset.from_list(train_entries).cast_column("audio", Audio(sampling_rate=16000))
    val_ds = Dataset.from_list(val_entries).cast_column("audio", Audio(sampling_rate=16000)) if val_entries else None

    # Preprocessing function
    def prepare_dataset(batch):
        audio = batch["audio"]
        input_features = processor.feature_extractor(
            audio["array"],
            sampling_rate=audio["sampling_rate"],
            return_tensors="np",
        ).input_features[0]

        labels = processor.tokenizer(batch["text"]).input_ids

        return {
            "input_features": input_features,
            "labels": labels,
        }

    train_ds = train_ds.map(prepare_dataset, remove_columns=train_ds.column_names)
    if val_ds:
        val_ds = val_ds.map(prepare_dataset, remove_columns=val_ds.column_names)

    # Data collator
    from dataclasses import dataclass
    from typing import Any, Dict, List, Union

    @dataclass
    class DataCollatorSpeechSeq2SeqWithPadding:
        processor: Any
        input_dtype: torch.dtype

        def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")
            batch["input_features"] = batch["input_features"].to(self.input_dtype)

            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

            labels = labels_batch["input_ids"].masked_fill(
                labels_batch.attention_mask.ne(1), -100
            )
            # Remove BOS token if present
            if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all():
                labels = labels[:, 1:]

            batch["labels"] = labels
            return batch

    input_dtype = model.dtype if device == "cuda" else torch.float32
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(
        processor=processor,
        input_dtype=input_dtype,
    )

    # WER metric
    wer_metric = evaluate.load("wer")

    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

        wer = 100 * wer_metric.compute(predictions=pred_str, references=label_str)
        return {"wer": wer}

    # Training arguments
    checkpoint_dir = os.path.join(CHECKPOINT_ROOT, "whisper-sheng")
    os.makedirs(checkpoint_dir, exist_ok=True)

    # transformers has used both `evaluation_strategy` and `eval_strategy`
    # across releases; detect and set the one supported in this environment.
    strategy_arg = "evaluation_strategy"
    training_arg_fields = inspect.signature(Seq2SeqTrainingArguments.__init__).parameters
    if "eval_strategy" in training_arg_fields:
        strategy_arg = "eval_strategy"

    training_kwargs = {
        "output_dir": checkpoint_dir,
        "per_device_train_batch_size": args.batch_size,
        "gradient_accumulation_steps": args.grad_accum,
        "learning_rate": args.lr,
        "warmup_steps": 50,
        "num_train_epochs": args.epochs,
        "fp16": True,
        "save_strategy": "epoch",
        "logging_steps": 10,
        "predict_with_generate": True,
        "generation_max_length": 225,
        "report_to": "none",
        "load_best_model_at_end": True if val_ds else False,
        "metric_for_best_model": "wer" if val_ds else None,
        "greater_is_better": False,
        "gradient_checkpointing": True,
        "remove_unused_columns": False,
    }
    training_kwargs[strategy_arg] = "epoch" if val_ds else "no"
    training_args = Seq2SeqTrainingArguments(**training_kwargs)

    # Trainer
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_ds,
        "eval_dataset": val_ds,
        "data_collator": data_collator,
        "compute_metrics": compute_metrics if val_ds else None,
    }

    trainer_arg_fields = inspect.signature(Seq2SeqTrainer.__init__).parameters
    if "processing_class" in trainer_arg_fields:
        trainer_kwargs["processing_class"] = processor
    else:
        trainer_kwargs["tokenizer"] = processor.feature_extractor

    trainer = Seq2SeqTrainer(**trainer_kwargs)

    # Train
    logger.info("Starting training...")
    trainer.train()

    # Save final LoRA adapter
    final_dir = os.path.join(checkpoint_dir, "final_adapter")
    model.save_pretrained(final_dir)
    processor.save_pretrained(final_dir)

    logger.info(f"Training complete! Adapter saved: {final_dir}")
    logger.info(f"Next: python brain/voice/training/export_stt.py --model {args.model}")

    if device == "cuda":
        peak_mem = torch.cuda.max_memory_allocated() / 1e9
        logger.info(f"Peak GPU memory: {peak_mem:.1f}GB")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Whisper for Kenyan phonetics")
    parser.add_argument("--model", default="whisper-small", help="Whisper model (whisper-small, whisper-medium)")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="STT dataset directory")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--grad-accum", type=int, default=2, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
