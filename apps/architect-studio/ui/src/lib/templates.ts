/**
 * Requirement templates for junior dev-friendly documentation
 */

export interface TemplateField {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'select' | 'multiselect' | 'boolean' | 'json' | 'array';
  placeholder?: string;
  options?: string[];
  required?: boolean;
  description?: string;
}

export interface RequirementTemplate {
  title: string;
  icon: string;
  description: string;
  fields: TemplateField[];
  generateDoc: (data: Record<string, any>) => string;
  generateFlowchart?: (data: Record<string, any>) => any[];
}

export const requirementTemplates: Record<string, RequirementTemplate> = {
  apiEndpoint: {
    title: "API Endpoint",
    icon: "🔌",
    description: "Document a REST API endpoint with request/response schemas",
    fields: [
      {
        name: "endpoint",
        label: "Endpoint Path",
        type: "text",
        placeholder: "/api/users/:id",
        required: true,
        description: "The URL path for this endpoint"
      },
      {
        name: "method",
        label: "HTTP Method",
        type: "select",
        options: ["GET", "POST", "PUT", "DELETE", "PATCH"],
        required: true
      },
      {
        name: "description",
        label: "What does this endpoint do?",
        type: "textarea",
        placeholder: "Retrieves user information by ID",
        required: true
      },
      {
        name: "authentication",
        label: "Requires Authentication?",
        type: "boolean"
      },
      {
        name: "requestBody",
        label: "Request Body Schema (JSON)",
        type: "json",
        placeholder: '{\n  "name": "string",\n  "email": "string"\n}'
      },
      {
        name: "responseSchema",
        label: "Response Schema (JSON)",
        type: "json",
        placeholder: '{\n  "id": "number",\n  "name": "string",\n  "email": "string"\n}'
      },
      {
        name: "errorCases",
        label: "Possible Error Cases",
        type: "multiselect",
        options: [
          "400 Bad Request - Invalid input",
          "401 Unauthorized - Not logged in",
          "403 Forbidden - No permission",
          "404 Not Found - Resource doesn't exist",
          "500 Server Error - Internal error"
        ]
      }
    ],
    generateDoc: (data) => `# API Endpoint: ${data.method} ${data.endpoint}

## Description
${data.description}

**Authentication**: ${data.authentication ? '✅ Required' : '❌ Not required'}

## Request

### Method
\`${data.method}\`

### Endpoint
\`${data.endpoint}\`

${data.requestBody ? `### Request Body
\`\`\`json
${data.requestBody}
\`\`\`
` : ''}

## Response

### Success (200 OK)
${data.responseSchema ? `\`\`\`json
${data.responseSchema}
\`\`\`
` : 'No response body'}

## Error Handling

${data.errorCases && data.errorCases.length > 0 ? data.errorCases.map((err: string) => `- **${err}**`).join('\n') : 'No specific error cases documented'}

## Example Usage

\`\`\`bash
curl -X ${data.method} \\
  ${data.authentication ? '-H "Authorization: Bearer YOUR_TOKEN" \\\n  ' : ''}https://api.example.com${data.endpoint}${data.requestBody ? ` \\\n  -H "Content-Type: application/json" \\\n  -d '${data.requestBody}'` : ''}
\`\`\`
`,
    generateFlowchart: (data) => [
      {
        id: 'req',
        type: 'requirement',
        position: { x: 100, y: 50 },
        data: {
          label: `${data.method} ${data.endpoint}`,
          description: data.description,
          acceptanceCriteria: data.errorCases || []
        }
      },
      {
        id: 'api',
        type: 'api',
        position: { x: 100, y: 200 },
        data: {
          method: data.method,
          endpoint: data.endpoint,
          auth: data.authentication
        }
      }
    ]
  },

  reactComponent: {
    title: "React Component",
    icon: "⚛️",
    description: "Document a React component with props, state, and hooks",
    fields: [
      {
        name: "componentName",
        label: "Component Name",
        type: "text",
        placeholder: "UserProfile",
        required: true
      },
      {
        name: "description",
        label: "What does this component do?",
        type: "textarea",
        placeholder: "Displays user profile information with edit capabilities",
        required: true
      },
      {
        name: "props",
        label: "Props (one per line)",
        type: "textarea",
        placeholder: "userId: string\nonEdit: () => void\nreadOnly?: boolean"
      },
      {
        name: "state",
        label: "State Variables (one per line)",
        type: "textarea",
        placeholder: "isEditing: boolean\nformData: UserData"
      },
      {
        name: "hooks",
        label: "Hooks Used",
        type: "multiselect",
        options: [
          "useState",
          "useEffect",
          "useContext",
          "useReducer",
          "useCallback",
          "useMemo",
          "useRef",
          "Custom hooks"
        ]
      },
      {
        name: "children",
        label: "Accepts Children?",
        type: "boolean"
      },
      {
        name: "styling",
        label: "Styling Approach",
        type: "select",
        options: ["Tailwind CSS", "CSS Modules", "Styled Components", "Inline Styles"]
      }
    ],
    generateDoc: (data) => `# Component: ${data.componentName}

## Description
${data.description}

## Props

${data.props ? data.props.split('\n').map((prop: string) => `- \`${prop}\``).join('\n') : 'No props'}

## State

${data.state ? data.state.split('\n').map((s: string) => `- \`${s}\``).join('\n') : 'No local state'}

## Hooks Used

${data.hooks && data.hooks.length > 0 ? data.hooks.map((hook: string) => `- ${hook}`).join('\n') : 'No hooks'}

## Styling
**Approach**: ${data.styling || 'Not specified'}

## Usage Example

\`\`\`tsx
import { ${data.componentName} } from './components/${data.componentName}';

function App() {
  return (
    <${data.componentName}${data.props ? `\n      ${data.props.split('\n')[0].split(':')[0]}="value"` : ''}${data.children ? '>\n      <p>Child content here</p>\n    </' + data.componentName + '>' : ' />'}
  );
}
\`\`\`
`,
    generateFlowchart: (data) => [
      {
        id: 'comp',
        type: 'component',
        position: { x: 100, y: 100 },
        data: {
          name: data.componentName,
          props: data.props ? data.props.split('\n') : [],
          state: data.state ? data.state.split('\n') : [],
          hooks: data.hooks || []
        }
      }
    ]
  },

  databaseModel: {
    title: "Database Model",
    icon: "🗄️",
    description: "Document a database table or model schema",
    fields: [
      {
        name: "modelName",
        label: "Model/Table Name",
        type: "text",
        placeholder: "users",
        required: true
      },
      {
        name: "description",
        label: "What does this model represent?",
        type: "textarea",
        placeholder: "Stores user account information",
        required: true
      },
      {
        name: "fields",
        label: "Fields (one per line: name:type)",
        type: "textarea",
        placeholder: "id:integer (primary key)\nname:string\nemail:string (unique)\ncreated_at:timestamp",
        required: true
      },
      {
        name: "relationships",
        label: "Relationships (one per line)",
        type: "textarea",
        placeholder: "has_many :posts\nbelongs_to :organization"
      },
      {
        name: "indexes",
        label: "Indexes (one per line)",
        type: "textarea",
        placeholder: "email (unique)\norganization_id, created_at"
      },
      {
        name: "validations",
        label: "Validations",
        type: "textarea",
        placeholder: "email must be valid format\nname required, min 2 chars"
      }
    ],
    generateDoc: (data) => `# Database Model: ${data.modelName}

## Description
${data.description}

## Schema

| Field | Type | Constraints |
|-------|------|-------------|
${data.fields ? data.fields.split('\n').map((field: string) => {
  const parts = field.split(':');
  const name = parts[0]?.trim() || '';
  const rest = parts.slice(1).join(':').trim();
  const typeMatch = rest.match(/^(\w+)/);
  const type = typeMatch ? typeMatch[1] : rest;
  const constraints = rest.replace(type, '').trim();
  return `| ${name} | ${type} | ${constraints || '-'} |`;
}).join('\n') : ''}

${data.relationships ? `## Relationships

${data.relationships.split('\n').map((rel: string) => `- ${rel}`).join('\n')}
` : ''}

${data.indexes ? `## Indexes

${data.indexes.split('\n').map((idx: string) => `- \`${idx}\``).join('\n')}
` : ''}

${data.validations ? `## Validations

${data.validations.split('\n').map((val: string) => `- ${val}`).join('\n')}
` : ''}

## Migration Example

\`\`\`sql
CREATE TABLE ${data.modelName} (
${data.fields ? data.fields.split('\n').map((field: string) => {
  const parts = field.split(':');
  const name = parts[0]?.trim();
  const rest = parts.slice(1).join(':').trim();
  return `  ${name} ${rest}`;
}).join(',\n') : ''}
);
\`\`\`
`,
    generateFlowchart: (data) => [
      {
        id: 'model',
        type: 'database',
        position: { x: 100, y: 100 },
        data: {
          name: data.modelName,
          fields: data.fields ? data.fields.split('\n') : [],
          relationships: data.relationships ? data.relationships.split('\n') : []
        }
      }
    ]
  },

  userStory: {
    title: "User Story",
    icon: "📋",
    description: "Document a user story with acceptance criteria",
    fields: [
      {
        name: "persona",
        label: "As a...",
        type: "text",
        placeholder: "junior developer",
        required: true
      },
      {
        name: "goal",
        label: "I want to...",
        type: "text",
        placeholder: "visualize my code structure",
        required: true
      },
      {
        name: "reason",
        label: "So that...",
        type: "text",
        placeholder: "I can understand the architecture better",
        required: true
      },
      {
        name: "acceptanceCriteria",
        label: "Acceptance Criteria (one per line)",
        type: "textarea",
        placeholder: "✓ User can view flowchart\n✓ User can export to PNG\n✓ User can add notes",
        required: true
      },
      {
        name: "priority",
        label: "Priority",
        type: "select",
        options: ["Critical", "High", "Medium", "Low"]
      },
      {
        name: "estimatedEffort",
        label: "Estimated Effort",
        type: "select",
        options: ["1 day", "2-3 days", "1 week", "2 weeks", "1 month"]
      }
    ],
    generateDoc: (data) => `# User Story

**As a** ${data.persona}
**I want to** ${data.goal}
**So that** ${data.reason}

## Acceptance Criteria

${data.acceptanceCriteria ? data.acceptanceCriteria.split('\n').map((criteria: string) => criteria.trim()).join('\n') : ''}

## Metadata

- **Priority**: ${data.priority || 'Not set'}
- **Estimated Effort**: ${data.estimatedEffort || 'Not estimated'}

## Implementation Notes

_Add implementation details here..._
`,
    generateFlowchart: (data) => [
      {
        id: 'story',
        type: 'requirement',
        position: { x: 100, y: 50 },
        data: {
          label: `User Story: ${data.persona}`,
          description: `${data.goal} so that ${data.reason}`,
          acceptanceCriteria: data.acceptanceCriteria ? data.acceptanceCriteria.split('\n') : [],
          priority: data.priority
        }
      }
    ]
  },

  bugReport: {
    title: "Bug Report",
    icon: "🐛",
    description: "Document a bug with reproduction steps",
    fields: [
      {
        name: "title",
        label: "Bug Title",
        type: "text",
        placeholder: "Login button not responding on mobile",
        required: true
      },
      {
        name: "severity",
        label: "Severity",
        type: "select",
        options: ["Critical", "High", "Medium", "Low"],
        required: true
      },
      {
        name: "description",
        label: "Description",
        type: "textarea",
        placeholder: "What's broken?",
        required: true
      },
      {
        name: "stepsToReproduce",
        label: "Steps to Reproduce (one per line)",
        type: "textarea",
        placeholder: "1. Open app on mobile\n2. Navigate to login page\n3. Tap login button\n4. Nothing happens",
        required: true
      },
      {
        name: "expectedBehavior",
        label: "Expected Behavior",
        type: "textarea",
        placeholder: "Login form should submit",
        required: true
      },
      {
        name: "actualBehavior",
        label: "Actual Behavior",
        type: "textarea",
        placeholder: "Button does not respond to touch",
        required: true
      },
      {
        name: "environment",
        label: "Environment",
        type: "text",
        placeholder: "iOS 17, Safari, iPhone 14"
      }
    ],
    generateDoc: (data) => `# Bug: ${data.title}

**Severity**: ${data.severity}
**Environment**: ${data.environment || 'Not specified'}

## Description
${data.description}

## Steps to Reproduce

${data.stepsToReproduce ? data.stepsToReproduce.split('\n').map((step: string) => step.trim()).join('\n') : ''}

## Expected Behavior
${data.expectedBehavior}

## Actual Behavior
${data.actualBehavior}

## Possible Solution

_Add debugging notes or potential fixes here..._
`,
    generateFlowchart: (data) => [
      {
        id: 'bug',
        type: 'requirement',
        position: { x: 100, y: 50 },
        data: {
          label: `🐛 ${data.title}`,
          description: data.description,
          acceptanceCriteria: [
            `Expected: ${data.expectedBehavior}`,
            `Actual: ${data.actualBehavior}`
          ],
          priority: data.severity
        }
      }
    ]
  }
};

export const techGlossary: Record<string, string> = {
  'API': 'Application Programming Interface - a way for different software to communicate',
  'REST': 'Representational State Transfer - a design pattern for APIs using HTTP methods',
  'MQTT': 'Message Queuing Telemetry Transport - lightweight pub/sub messaging protocol for IoT',
  'STT': 'Speech-to-Text - converts spoken audio into written text',
  'TTS': 'Text-to-Speech - converts written text into spoken audio',
  'Webhook': 'An HTTP callback that occurs when something happens, allowing real-time notifications',
  'JWT': 'JSON Web Token - a secure way to transmit information between parties',
  'OAuth': 'Open Authorization - a standard for access delegation, commonly used for "login with Google"',
  'SSR': 'Server-Side Rendering - generating HTML on the server instead of in the browser',
  'CSR': 'Client-Side Rendering - generating HTML in the browser using JavaScript',
  'PWA': 'Progressive Web App - a web app that works like a native mobile app',
  'WebSocket': 'A protocol for two-way real-time communication between client and server',
  'LoRA': 'Low-Rank Adaptation - efficient fine-tuning technique for large language models',
  'ONNX': 'Open Neural Network Exchange - format for machine learning models',
  'VAD': 'Voice Activity Detection - determines when someone is speaking',
  'Embedding': 'A way to represent data (text, images, etc.) as numbers for AI processing',
  'Fine-tuning': 'Training a pre-trained AI model on specific data to specialize it',
  'Inference': 'Using a trained AI model to make predictions or generate outputs',
  'Latency': 'The delay between an action and its response',
  'Throughput': 'The amount of data processed in a given time period',
  'Tokenization': 'Breaking text into smaller pieces (tokens) for AI processing',
  'Schema': 'The structure/blueprint defining how data is organized',
  'Migration': 'A way to modify database structure over time while preserving data',
  'Middleware': 'Software that sits between different systems to facilitate communication',
  'State': 'Data that changes over time in your application',
  'Props': 'Short for properties - data passed from parent to child components in React',
  'Hook': 'React function that lets you use state and lifecycle features in functional components',
  'Component': 'A reusable piece of UI in React or other frameworks',
  'Deployment': 'Making your application available for use (putting it "live")',
  'Repository': 'A storage location for code, usually managed by Git',
  'Commit': 'A snapshot of your code at a specific point in time',
  'Branch': 'A parallel version of your code for working on features independently',
  'Merge': 'Combining changes from different branches',
  'Pull Request': 'A request to merge your code changes into another branch',
  'Edge Computing': 'Processing data closer to where it\'s generated (like on a Jetson device) instead of in the cloud',
  'Semantic Search': 'Search that understands meaning, not just exact word matches',
  'Vector Database': 'A database optimized for storing and searching AI embeddings',
  'Feature': 'New functionality or capability added to software',
  'Refactor': 'Improving code structure without changing its behavior',
  'Bug': 'An error or flaw in software that causes incorrect behavior',
  'Test': 'Code that verifies other code works correctly',
  'CI/CD': 'Continuous Integration/Continuous Deployment - automated building, testing, and deploying',
  'Docker': 'A tool for packaging applications with all their dependencies',
  'Container': 'A lightweight, isolated environment for running applications',
  'Kubernetes': 'A system for automating deployment and management of containerized applications',
  'AI': 'Artificial Intelligence - computer systems that can perform tasks requiring human-like intelligence'
};
