import Link from "next/link";

export default function OverviewPage() {
  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <Link href="/" className="text-sm underline">
          ← Back to Home
        </Link>
      </div>

      <h1 className="text-2xl font-semibold">Overview</h1>
      <p className="mt-2 text-sm opacity-70">Route OK: /overview</p>
    </main>
  );
}
