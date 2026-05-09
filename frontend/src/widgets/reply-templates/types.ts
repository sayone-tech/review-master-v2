export interface TemplateRow {
  id: number;
  name: string;
  content: string;
  created_at: string;
}

export interface CreateTemplatePayload {
  name: string;
  content: string;
}

export interface UpdateTemplatePayload {
  name?: string;
  content?: string;
}
