"use client";

import type { ChangeEvent } from "react";

type KnowledgeTasksSectionProps = {
  uploadState: string;
  uploading: boolean;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  onBuildDocs: () => void;
};

export function KnowledgeTasksSection({ uploadState, uploading, onUpload, onBuildDocs }: KnowledgeTasksSectionProps) {
  return (
    <div className="summary-section">
      <h3>知识库任务</h3>
      <p>构建文档索引时会同时纳入本地 policy/spec、Confluence 文档和 Jira 文档切片。</p>
      <div className="status-line">上传状态: {uploadState}</div>
      <div className="field" style={{ marginTop: 12 }}>
        <label htmlFor="task-upload-docs">上传 policy/spec 文档</label>
        <input
          id="task-upload-docs"
          type="file"
          multiple
          onChange={onUpload}
          disabled={uploading}
          accept=".md,.markdown,.txt,.pdf,.docx,.pptx,.xlsx,.csv"
        />
      </div>
      <p>支持格式：`.md`、`.txt`、`.pdf`、`.docx`、`.pptx`、`.xlsx`、`.csv`。上传后仍需手动执行“构建文档索引”。</p>
      <div className="settings-stack">
        <button className="secondary-button" type="button" onClick={onBuildDocs}>
          构建文档索引
        </button>
      </div>
    </div>
  );
}
