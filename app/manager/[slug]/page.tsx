import fs from "fs";
import path from "path";
import Link from "next/link";

const DATA_DIR = path.join(process.cwd(), "data", "13f");

type ManagerData = {
  name?: string;
  latest?: { quarter?: string; filing_date?: string };
  stats?: { holdings?: number; top1?: string };
  holdings?: Array<{ issuer: string; value_usd_k: number; weight: number; shares: number; cusip?: string | null }>;
};

export default async function ManagerDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const filePath = path.join(DATA_DIR, `${slug}.json`);

  let data: ManagerData | null = null;
  try {
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf-8");
      data = JSON.parse(raw) as ManagerData;
    }
  } catch {
    data = null;
  }

  if (!data) {
    return (
      <main className="mx-auto max-w-5xl p-6">
        <div className="mb-6">
          <Link href="/overview" className="text-sm underline text-[#4ADE80]">
            ← Back to Overview
          </Link>
        </div>
        <h1 className="text-xl font-semibold">Manager not found</h1>
        <p className="mt-4 text-[#F9FAFB] opacity-80">No data for slug: {slug}</p>
      </main>
    );
  }

  const name = data.name || slug;
  const quarter = data.latest?.quarter || "";
  const filingDate = data.latest?.filing_date || "";
  const holdings = data.holdings || [];
  const top1 = data.stats?.top1;

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center gap-4">
        <Link href="/overview" className="text-sm underline text-[#4ADE80]">
          ← Back to Overview
        </Link>
        <Link
          href={`/manager/${slug}/movers`}
          className="text-sm font-medium text-[#4ADE80] hover:underline"
        >
          Top Movers →
        </Link>
      </div>
      <h1 className="text-xl font-semibold">{name}</h1>
      <p className="text-sm opacity-70 mt-1">
        {quarter ? `Latest: ${quarter}` : ""}
        {filingDate ? ` · Filed ${filingDate}` : ""}
      </p>
      {top1 && (
        <p className="text-sm opacity-60 mt-1">Top holding: {top1}</p>
      )}
      <p className="text-sm opacity-60 mt-2">
        {holdings.length} holdings
      </p>
    </main>
  );
}
