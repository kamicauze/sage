export interface GmailMessageRef {
  id: string;
  threadId: string;
}

export interface GmailMessagesResponse {
  success: boolean;
  count: number;
  messages: GmailMessageRef[];
}

export interface GmailMessageHeader {
  name: string;
  value: string;
}

export interface GmailMessagePart {
  mimeType: string;
  body?: { data?: string; size?: number };
  parts?: GmailMessagePart[];
}

export interface GmailMessagePayload {
  headers?: GmailMessageHeader[];
  mimeType?: string;
  body?: { data?: string; size?: number };
  parts?: GmailMessagePart[];
}

export interface GmailMessage {
  id: string;
  threadId: string;
  labelIds?: string[];
  snippet?: string;
  payload?: GmailMessagePayload;
  internalDate?: string;
  sizeEstimate?: number;
}

export interface GmailMessageResponse {
  success: boolean;
  message: GmailMessage;
}

export interface GmailSendResponse {
  success: boolean;
  message_id: string;
}

export interface GmailModifyResponse {
  success: boolean;
  message: GmailMessage;
}
