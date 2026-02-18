'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Trash2, Save } from 'lucide-react';

interface Zone {
  name: string;
  role: 'truth' | 'soul' | 'hands' | 'body';
  paths: string[];
}

export default function NewProjectPage() {
  const router = useRouter();
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [description, setDescription] = useState('');
  const [repoPath, setRepoPath] = useState('');
  const [primaryLanguage, setPrimaryLanguage] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [zones, setZones] = useState<Zone[]>([
    { name: '', role: 'truth', paths: [''] },
  ]);
  const [monthlyBudget, setMonthlyBudget] = useState('120.0');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const addZone = () => {
    setZones([...zones, { name: '', role: 'truth', paths: [''] }]);
  };

  const removeZone = (index: number) => {
    setZones(zones.filter((_, i) => i !== index));
  };

  const updateZone = (index: number, field: keyof Zone, value: any) => {
    const updated = [...zones];
    updated[index] = { ...updated[index], [field]: value };
    setZones(updated);
  };

  const addZonePath = (zoneIndex: number) => {
    const updated = [...zones];
    updated[zoneIndex].paths.push('');
    setZones(updated);
  };

  const removeZonePath = (zoneIndex: number, pathIndex: number) => {
    const updated = [...zones];
    updated[zoneIndex].paths = updated[zoneIndex].paths.filter((_, i) => i !== pathIndex);
    setZones(updated);
  };

  const updateZonePath = (zoneIndex: number, pathIndex: number, value: string) => {
    const updated = [...zones];
    updated[zoneIndex].paths[pathIndex] = value;
    setZones(updated);
  };

  const addTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput('');
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const generateYAML = () => {
    const manifest = {
      schema_version: '1.1',
      project: {
        id: projectId,
        name: projectName,
        description: description,
        paths: {
          repo_path: repoPath,
        },
      },
      stack: {
        primary: primaryLanguage,
        tags: tags,
      },
      memory: {
        enabled: true,
        zones: zones.map((zone) => ({
          name: zone.name,
          role: zone.role,
          paths: zone.paths.filter((p) => p.trim() !== ''),
        })),
      },
      commands: {
        install: [],
        build: [],
        test: [],
      },
      policy: {
        ai_budget: {
          monthly_usd: parseFloat(monthlyBudget),
        },
        routing_thresholds: {
          hybrid_score: 4,
          cloud_score: 8,
        },
      },
    };

    return JSON.stringify(manifest, null, 2);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!projectId.match(/^[a-z0-9_]+$/)) {
      setError('Project ID must contain only lowercase letters, numbers, and underscores');
      return;
    }

    if (zones.some((z) => !z.name.trim())) {
      setError('All zones must have a name');
      return;
    }

    if (zones.some((z) => z.paths.filter((p) => p.trim()).length === 0)) {
      setError('All zones must have at least one path');
      return;
    }

    try {
      // Generate YAML content
      const yamlContent = generateYAML();

      // Create the project manifest via API
      const response = await fetch('http://localhost:8000/projects/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          manifest_content: yamlContent,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create project');
      }

      setSuccess(true);
      setTimeout(() => {
        router.push('/');
        window.location.reload(); // Reload to refresh project list
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
    }
  };

  const roleDescriptions = {
    truth: 'Core Logic - Business logic, algorithms, core functionality',
    soul: 'User Interface - UI components, interactions, personalities',
    hands: 'Execution - Database ops, API clients, external integrations',
    body: 'Infrastructure - Deployment, config, CI/CD, monitoring',
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Create New Project</h1>
        <p className="text-gray-400">
          Configure a new project manifest for the Architect system
        </p>
      </div>

      {success && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400">
          ✓ Project created successfully! Redirecting...
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Basic Information</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Project ID *
                <span className="text-xs text-gray-400 ml-2">
                  (lowercase, underscores only)
                </span>
              </label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder="my_awesome_project"
                className="input w-full"
                required
                pattern="[a-z0-9_]+"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Project Name *</label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="My Awesome Project"
                className="input w-full"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this project does..."
                className="input w-full h-20 resize-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Repository Path *
                <span className="text-xs text-gray-400 ml-2">
                  (absolute or relative)
                </span>
              </label>
              <input
                type="text"
                value={repoPath}
                onChange={(e) => setRepoPath(e.target.value)}
                placeholder="/home/user/projects/my-project"
                className="input w-full font-mono text-sm"
                required
              />
            </div>
          </div>
        </div>

        {/* Stack */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Technology Stack</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Primary Language *</label>
              <select
                value={primaryLanguage}
                onChange={(e) => setPrimaryLanguage(e.target.value)}
                className="input w-full"
                required
              >
                <option value="">Select language...</option>
                <option value="python">Python</option>
                <option value="typescript">TypeScript</option>
                <option value="javascript">JavaScript</option>
                <option value="go">Go</option>
                <option value="rust">Rust</option>
                <option value="java">Java</option>
                <option value="csharp">C#</option>
                <option value="ruby">Ruby</option>
                <option value="php">PHP</option>
                <option value="swift">Swift</option>
                <option value="kotlin">Kotlin</option>
                <option value="unity">Unity</option>
                <option value="unreal">Unreal</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Tags</label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  placeholder="web, api, react, etc."
                  className="input flex-1"
                />
                <button
                  type="button"
                  onClick={addTag}
                  className="btn-secondary"
                >
                  <Plus size={16} />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="badge badge-local flex items-center gap-2"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="hover:text-red-400"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Cognitive Zones */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">Cognitive Zones</h2>
            <button
              type="button"
              onClick={addZone}
              className="btn-secondary flex items-center gap-2"
            >
              <Plus size={16} />
              Add Zone
            </button>
          </div>

          <div className="space-y-4">
            {zones.map((zone, zoneIdx) => (
              <div
                key={zoneIdx}
                className="p-4 bg-architect-dark rounded-lg border border-architect-border"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium mb-1">Zone Name *</label>
                        <input
                          type="text"
                          value={zone.name}
                          onChange={(e) => updateZone(zoneIdx, 'name', e.target.value)}
                          placeholder="API Layer"
                          className="input w-full text-sm"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium mb-1">Role *</label>
                        <select
                          value={zone.role}
                          onChange={(e) => updateZone(zoneIdx, 'role', e.target.value)}
                          className="input w-full text-sm"
                          required
                        >
                          <option value="truth">Truth (Core Logic)</option>
                          <option value="soul">Soul (UI)</option>
                          <option value="hands">Hands (Execution)</option>
                          <option value="body">Body (Infrastructure)</option>
                        </select>
                      </div>
                    </div>

                    <div className="text-xs text-gray-400">
                      {roleDescriptions[zone.role]}
                    </div>

                    <div>
                      <label className="block text-xs font-medium mb-1">Paths *</label>
                      {zone.paths.map((path, pathIdx) => (
                        <div key={pathIdx} className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={path}
                            onChange={(e) => updateZonePath(zoneIdx, pathIdx, e.target.value)}
                            placeholder="src/api/**/*.ts"
                            className="input flex-1 text-sm font-mono"
                            required
                          />
                          {zone.paths.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeZonePath(zoneIdx, pathIdx)}
                              className="btn-secondary px-2"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => addZonePath(zoneIdx)}
                        className="text-xs text-architect-accent hover:text-blue-300"
                      >
                        + Add path
                      </button>
                    </div>
                  </div>

                  {zones.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeZone(zoneIdx)}
                      className="ml-3 text-red-400 hover:text-red-300"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Policy */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">AI Budget Policy</h2>

          <div>
            <label className="block text-sm font-medium mb-2">
              Monthly Budget (USD)
            </label>
            <input
              type="number"
              step="0.01"
              value={monthlyBudget}
              onChange={(e) => setMonthlyBudget(e.target.value)}
              className="input w-full"
              required
            />
            <p className="text-xs text-gray-400 mt-1">
              Recommended: $120/month for active development
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            type="submit"
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            <Save size={20} />
            Create Project
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="btn-secondary"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
