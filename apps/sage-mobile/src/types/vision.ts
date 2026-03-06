export interface VisionLatestResponse {
  success: boolean;
  location: string;
  mqtt_online: boolean;
  mqtt_error?: string | null;
  frame_available: boolean;
  image_base64?: string | null;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  people_count: number;
  face_detected: boolean;
  activity: string;
  mood: string;
  objects: string[];
  scene_description: string;
  frame_timestamp?: number | null;
  stale_seconds?: number | null;
}

export interface VisionScanResponse {
  success: boolean;
  location: string;
  mqtt_online: boolean;
  mqtt_error?: string | null;
  topic: string;
}
