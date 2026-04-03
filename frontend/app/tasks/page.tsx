import { TaskCenterClient } from "./TaskCenterClient";

export default function TaskCenterPage() {
  return (
    <main>
      <section className="hero">
        <h1>任务中心</h1>
        <p>
          在一个页面里统一发起 Jira 同步、Confluence 同步、文档上传、文档索引构建、日报分析、日报导出和项目管理摘要任务，
          并查看最近运行记录。
        </p>
      </section>
      <TaskCenterClient />
    </main>
  );
}
