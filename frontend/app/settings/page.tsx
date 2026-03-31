import { SettingsClient } from "./SettingsClient";

export default function SettingsPage() {
  return (
    <main>
      <section className="hero">
        <h1>Prompt Settings</h1>
        <p>统一配置默认语言、全局输出长度、场景级 token 上限和 custom prompt。</p>
      </section>
      <SettingsClient />
    </main>
  );
}
