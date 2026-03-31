"use client";

import { useEffect, useState } from "react";
import { getPromptSettings, updatePromptSettings, type PromptSettings } from "@/lib/api";

const scenarios = ["daily_report", "issue_deep_analysis", "docs_qa", "jira_docs_qa", "management_summary"];

export function SettingsClient() {
  const [settings, setSettings] = useState<PromptSettings | null>(null);
  const [status, setStatus] = useState<string>("加载中");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getPromptSettings()
      .then((result) => {
        setSettings(result);
        setStatus("已加载");
      })
      .catch((error) => {
        setStatus(error instanceof Error ? error.message : "加载失败");
      });
  }, []);

  if (!settings) {
    return <div className="panel empty-state">{status}</div>;
  }

  async function handleSave() {
    if (!settings) {
      return;
    }
    setSaving(true);
    try {
      const result = await updatePromptSettings(settings);
      setSettings(result);
      setStatus("已保存");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="panel">
      <div className="status-line">{status}</div>
      <div className="settings-grid" style={{ marginTop: 18 }}>
        <div className="field">
          <label htmlFor="default-language">默认语言</label>
          <input
            id="default-language"
            value={settings.default_language}
            onChange={(e) => setSettings({ ...settings, default_language: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="max-output-tokens">全局 max_output_tokens</label>
          <input
            id="max-output-tokens"
            type="number"
            value={settings.max_output_tokens}
            onChange={(e) => setSettings({ ...settings, max_output_tokens: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="summary-section">
        <h2>场景 token 上限</h2>
        <div className="settings-grid">
          {scenarios.map((scenario) => (
            <div key={scenario} className="field">
              <label htmlFor={`token-${scenario}`}>{scenario}</label>
              <input
                id={`token-${scenario}`}
                type="number"
                value={settings.scenario_max_output_tokens[scenario] ?? ""}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    scenario_max_output_tokens: {
                      ...settings.scenario_max_output_tokens,
                      [scenario]: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
          ))}
        </div>
      </div>

      <div className="summary-section">
        <h2>Custom Prompts</h2>
        <div className="settings-stack">
          {scenarios.map((scenario) => (
            <div key={scenario} className="field">
              <label htmlFor={`prompt-${scenario}`}>{scenario}</label>
              <textarea
                id={`prompt-${scenario}`}
                className="prompt-editor"
                value={settings.custom_prompts[scenario] ?? ""}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    custom_prompts: {
                      ...settings.custom_prompts,
                      [scenario]: e.target.value,
                    },
                  })
                }
              />
            </div>
          ))}
        </div>
      </div>

      <div className="summary-section">
        <button className="primary-button" type="button" onClick={handleSave} disabled={saving}>
          {saving ? "保存中..." : "保存设置"}
        </button>
      </div>
    </div>
  );
}
