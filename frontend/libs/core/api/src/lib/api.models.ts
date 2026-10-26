/** RFC 7807 problem details: the body of every API error. */
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  traceId?: string;
  /** Validation errors keyed by field name. */
  errors?: Record<string, string[]>;
}
