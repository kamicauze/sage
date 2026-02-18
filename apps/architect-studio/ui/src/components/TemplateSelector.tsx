'use client';

import { useState } from 'react';
import { requirementTemplates, TemplateField } from '@/lib/templates';
import { X, Copy, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface TemplateSelectorProps {
  onGenerate: (documentation: string, flowchartData?: any[]) => void;
  onClose: () => void;
}

export function TemplateSelector({ onGenerate, onClose }: TemplateSelectorProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [preview, setPreview] = useState<string>('');

  const handleTemplateSelect = (templateKey: string) => {
    setSelectedTemplate(templateKey);
    setFormData({});
    setPreview('');
  };

  const handleFieldChange = (fieldName: string, value: any) => {
    setFormData((prev) => ({ ...prev, [fieldName]: value }));
  };

  const handlePreview = () => {
    if (!selectedTemplate) return;
    const template = requirementTemplates[selectedTemplate];
    const doc = template.generateDoc(formData);
    setPreview(doc);
  };

  const handleGenerate = () => {
    if (!selectedTemplate) return;
    const template = requirementTemplates[selectedTemplate];
    const doc = template.generateDoc(formData);
    const flowchart = template.generateFlowchart?.(formData);
    onGenerate(doc, flowchart);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(preview);
  };

  if (!selectedTemplate) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-architect-gray rounded-2xl border border-architect-border max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="p-6 border-b border-architect-border flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold mb-1">Choose a Documentation Template</h2>
              <p className="text-sm text-gray-400">
                Select a template to get started with structured documentation
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Template Grid */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(requirementTemplates).map(([key, template]) => (
                <button
                  key={key}
                  onClick={() => handleTemplateSelect(key)}
                  className="card p-6 hover:border-architect-accent transition-all text-left group"
                >
                  <div className="text-4xl mb-3">{template.icon}</div>
                  <h3 className="font-semibold mb-2 group-hover:text-architect-accent transition-colors">
                    {template.title}
                  </h3>
                  <p className="text-sm text-gray-400">{template.description}</p>
                  <div className="mt-4 text-xs text-architect-accent opacity-0 group-hover:opacity-100 transition-opacity">
                    Click to use this template →
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const template = requirementTemplates[selectedTemplate];

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-architect-gray rounded-2xl border border-architect-border max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-architect-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSelectedTemplate(null)}
              className="px-3 py-1 text-sm hover:bg-white/5 rounded transition-colors"
            >
              ← Back
            </button>
            <div className="text-2xl">{template.icon}</div>
            <div>
              <h2 className="text-xl font-semibold">{template.title}</h2>
              <p className="text-sm text-gray-400">{template.description}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/5 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* Form */}
          <div className="flex-1 overflow-y-auto p-6 border-r border-architect-border">
            <h3 className="font-semibold mb-4">Fill in the details:</h3>
            <div className="space-y-4">
              {template.fields.map((field) => (
                <TemplateFieldInput
                  key={field.name}
                  field={field}
                  value={formData[field.name]}
                  onChange={(value) => handleFieldChange(field.name, value)}
                />
              ))}
            </div>

            <div className="flex gap-2 mt-6">
              <button onClick={handlePreview} className="btn-secondary flex-1">
                <FileText className="w-4 h-4 inline mr-2" />
                Preview
              </button>
              <button onClick={handleGenerate} className="btn-primary flex-1">
                Generate Documentation
              </button>
            </div>
          </div>

          {/* Preview */}
          <div className="flex-1 overflow-y-auto p-6 bg-architect-dark">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Preview:</h3>
              {preview && (
                <button
                  onClick={copyToClipboard}
                  className="p-2 hover:bg-white/5 rounded transition-colors"
                  title="Copy to clipboard"
                >
                  <Copy className="w-4 h-4" />
                </button>
              )}
            </div>

            {preview ? (
              <div className="prose prose-invert max-w-none">
                <ReactMarkdown>{preview}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Fill in the form and click &quot;Preview&quot; to see your documentation</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

interface TemplateFieldInputProps {
  field: TemplateField;
  value: any;
  onChange: (value: any) => void;
}

function TemplateFieldInput({ field, value, onChange }: TemplateFieldInputProps) {
  const renderInput = () => {
    switch (field.type) {
      case 'text':
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
            className="input w-full"
          />
        );

      case 'textarea':
        return (
          <textarea
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
            className="input w-full h-24 resize-none"
          />
        );

      case 'select':
        return (
          <select
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            required={field.required}
            className="input w-full"
          >
            <option value="">Select...</option>
            {field.options?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        );

      case 'multiselect':
        return (
          <div className="space-y-2">
            {field.options?.map((option) => (
              <label key={option} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={value?.includes(option) || false}
                  onChange={(e) => {
                    const current = value || [];
                    if (e.target.checked) {
                      onChange([...current, option]);
                    } else {
                      onChange(current.filter((v: string) => v !== option));
                    }
                  }}
                  className="w-4 h-4 rounded border-architect-border"
                />
                <span className="text-sm">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'boolean':
        return (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={value || false}
              onChange={(e) => onChange(e.target.checked)}
              className="w-4 h-4 rounded border-architect-border"
            />
            <span className="text-sm">Yes</span>
          </label>
        );

      case 'json':
        return (
          <textarea
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={field.placeholder}
            required={field.required}
            className="input w-full h-32 resize-none font-mono text-sm"
          />
        );

      default:
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            className="input w-full"
          />
        );
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        {field.label}
        {field.required && <span className="text-red-400 ml-1">*</span>}
      </label>
      {field.description && (
        <p className="text-xs text-gray-500 mb-2">{field.description}</p>
      )}
      {renderInput()}
    </div>
  );
}
