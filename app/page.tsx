import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">13F Dashboard v2</h1>
      <p>
        <Link href="/overview" className="text-[#4ADE80] underline">
          Go to Overview
        </Link>
      </p>
    </div>
  );
}
