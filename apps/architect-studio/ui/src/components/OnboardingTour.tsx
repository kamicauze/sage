'use client';

import { useState, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';

export interface TourStep {
  target: string; // CSS selector
  title: string;
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  image?: string;
}

interface OnboardingTourProps {
  steps: TourStep[];
  onComplete?: () => void;
  onSkip?: () => void;
  storageKey?: string;
}

export function OnboardingTour({
  steps,
  onComplete,
  onSkip,
  storageKey = 'tour-completed',
}: OnboardingTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    // Check if tour was already completed
    const completed = localStorage.getItem(storageKey);
    if (!completed) {
      setTimeout(() => setIsVisible(true), 500);
    }
  }, [storageKey]);

  useEffect(() => {
    if (!isVisible) return;

    const updateTargetRect = () => {
      const step = steps[currentStep];
      const element = document.querySelector(step.target);
      if (element) {
        setTargetRect(element.getBoundingClientRect());
      }
    };

    updateTargetRect();
    window.addEventListener('resize', updateTargetRect);
    window.addEventListener('scroll', updateTargetRect);

    return () => {
      window.removeEventListener('resize', updateTargetRect);
      window.removeEventListener('scroll', updateTargetRect);
    };
  }, [isVisible, currentStep, steps]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleComplete = () => {
    localStorage.setItem(storageKey, 'true');
    setIsVisible(false);
    onComplete?.();
  };

  const handleSkip = () => {
    localStorage.setItem(storageKey, 'true');
    setIsVisible(false);
    onSkip?.();
  };

  if (!isVisible || steps.length === 0) return null;

  const step = steps[currentStep];
  const progress = ((currentStep + 1) / steps.length) * 100;

  // Calculate tooltip position
  const getTooltipStyle = (): React.CSSProperties => {
    if (!targetRect) return { display: 'none' };

    const position = step.position || 'bottom';
    const offset = 16;

    switch (position) {
      case 'top':
        return {
          bottom: `${window.innerHeight - targetRect.top + offset}px`,
          left: `${targetRect.left + targetRect.width / 2}px`,
          transform: 'translateX(-50%)',
        };
      case 'bottom':
        return {
          top: `${targetRect.bottom + offset}px`,
          left: `${targetRect.left + targetRect.width / 2}px`,
          transform: 'translateX(-50%)',
        };
      case 'left':
        return {
          top: `${targetRect.top + targetRect.height / 2}px`,
          right: `${window.innerWidth - targetRect.left + offset}px`,
          transform: 'translateY(-50%)',
        };
      case 'right':
        return {
          top: `${targetRect.top + targetRect.height / 2}px`,
          left: `${targetRect.right + offset}px`,
          transform: 'translateY(-50%)',
        };
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] animate-in fade-in duration-300" />

      {/* Spotlight */}
      {targetRect && (
        <div
          className="fixed z-[101] pointer-events-none"
          style={{
            top: targetRect.top - 4,
            left: targetRect.left - 4,
            width: targetRect.width + 8,
            height: targetRect.height + 8,
            boxShadow: '0 0 0 4px rgba(59, 130, 246, 0.5), 0 0 0 9999px rgba(0, 0, 0, 0.6)',
            borderRadius: '8px',
            transition: 'all 0.3s ease',
          }}
        />
      )}

      {/* Tooltip */}
      <div
        className="fixed z-[102] w-full max-w-md px-4"
        style={getTooltipStyle()}
      >
        <div className="card bg-architect-gray/95 backdrop-blur-md border-architect-accent shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="font-semibold text-lg">{step.title}</h3>
              <p className="text-xs text-gray-400 mt-1">
                Step {currentStep + 1} of {steps.length}
              </p>
            </div>
            <button
              onClick={handleSkip}
              className="p-1 hover:bg-white/10 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-architect-border rounded-full h-1 mb-4">
            <div
              className="bg-architect-accent h-full rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Content */}
          <p className="text-sm text-gray-300 mb-4">{step.content}</p>

          {step.image && (
            <img
              src={step.image}
              alt={step.title}
              className="rounded-lg mb-4 w-full"
            />
          )}

          {/* Navigation */}
          <div className="flex items-center justify-between gap-2">
            <button
              onClick={handleSkip}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Skip Tour
            </button>

            <div className="flex gap-2">
              {currentStep > 0 && (
                <button onClick={handlePrevious} className="btn-secondary px-3 py-2">
                  <ChevronLeft className="w-4 h-4" />
                </button>
              )}
              <button onClick={handleNext} className="btn-primary px-4 py-2">
                {currentStep < steps.length - 1 ? (
                  <>
                    Next
                    <ChevronRight className="w-4 h-4 ml-1 inline" />
                  </>
                ) : (
                  'Get Started'
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Arrow pointer */}
        {step.position === 'bottom' && (
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-architect-gray/95 border-t border-l border-architect-accent rotate-45" />
        )}
        {step.position === 'top' && (
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-architect-gray/95 border-b border-r border-architect-accent rotate-45" />
        )}
        {step.position === 'right' && (
          <div className="absolute -left-2 top-1/2 -translate-y-1/2 w-4 h-4 bg-architect-gray/95 border-l border-b border-architect-accent rotate-45" />
        )}
        {step.position === 'left' && (
          <div className="absolute -right-2 top-1/2 -translate-y-1/2 w-4 h-4 bg-architect-gray/95 border-r border-t border-architect-accent rotate-45" />
        )}
      </div>
    </>
  );
}

// Tour step definitions for the Build page
export const buildPageTour: TourStep[] = [
  {
    target: '.build-query-input',
    title: 'Describe What You Need',
    content:
      'Start by describing what you want to build in plain English. Be as detailed as possible! For example: "Add a user authentication API with JWT tokens"',
    position: 'bottom',
  },
  {
    target: '.request-type-selector',
    title: 'Choose Request Type',
    content:
      'Select the type of change: Feature (new functionality), Bugfix (fix something broken), Refactor (improve code), or Test (add tests).',
    position: 'bottom',
  },
  {
    target: '.template-button',
    title: 'Use Templates',
    content:
      'Not sure where to start? Click here to use pre-built templates for common documentation patterns like API endpoints, React components, and more!',
    position: 'left',
  },
  {
    target: '.flowchart-tab',
    title: 'Visual Planning',
    content:
      'Switch to the Flowchart tab to create visual diagrams of your architecture. Perfect for understanding complex workflows!',
    position: 'bottom',
  },
  {
    target: '.generate-plan-button',
    title: 'Generate Your Plan',
    content:
      'Once you\'re ready, click here to generate an AI-powered implementation plan. The system will analyze your codebase and create a step-by-step plan.',
    position: 'top',
  },
];
