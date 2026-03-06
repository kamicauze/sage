export interface VaultKeysResponse {
  success: boolean;
  count: number;
  keys: string[];
}

export interface VaultStoreResponse {
  success: boolean;
  name: string;
}

export interface VaultRetrieveResponse {
  success: boolean;
  name: string;
  value: string;
}

export interface VaultDeleteResponse {
  success: boolean;
  deleted: string;
}
