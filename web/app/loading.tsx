export default function Loading() {
  return (
    <main aria-busy="true" className="grid gap-4">
      <div className="skeleton h-6 w-48" />
      <div className="skeleton h-10 w-72" />
      <div className="table-card">
        <div className="skeleton h-10 w-full rounded-none" />
        <div className="skeleton h-12 w-full rounded-none" />
        <div className="skeleton h-12 w-full rounded-none" />
        <div className="skeleton h-12 w-full rounded-none" />
      </div>
    </main>
  );
}
