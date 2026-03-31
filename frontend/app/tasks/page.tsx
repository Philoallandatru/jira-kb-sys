import { TaskCenterClient } from "./TaskCenterClient";

export default function TaskCenterPage() {
  return (
    <main>
      <section className="hero">
        <h1>Task Center</h1>
        <p>
          Launch operational jobs from one place, inspect recent runs, and use this page as the shared control
          surface for sync, indexing, analysis, reporting, and management summary generation.
        </p>
      </section>
      <TaskCenterClient />
    </main>
  );
}
