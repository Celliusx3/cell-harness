/** The skill wire types, mirroring `backend/harness/web/routes/skills.py`. */

export interface SkillSummary {
  name: string;
  description: string;
  dir: string;
  root: string;
  model_invocable: boolean;
  user_invocable: boolean;
  /** In `skills.editable`, so the page may save over it or delete it. */
  editable: boolean;
}

interface SkillIssue {
  path: string;
  problem: string;
}

export interface SkillList {
  skills: SkillSummary[];
  problems: SkillIssue[];
}

export interface SkillFile {
  name: string;
  text: string;
  editable: boolean;
  files: string[];
}

/** `GET /api/skills/{name}/files/{path}` */
export interface BundledFile {
  path: string;
  text: string;
}
