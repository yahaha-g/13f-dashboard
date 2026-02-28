import fs from "fs";
import path from "path";
import Link from "next/link";

const DATA_DIR = path.join(process.cwd(), "data", "13f", "diff");

type DiffItem = {
  issuer: string;
  cusip: string | null;
  value_prev: number;
  value_now: number;
  value_delta: number;
  weight_prev: number;
  weight_now: number;
  weight_delta: number;
  shares_prev: number;
  shares_now: number;
  shares_delta: number;
  action: string;
};

type DiffPayload = {
  slug: string;
  name: string;
  quarter_now: string;
  quarter_prev: string;
  filing_date_now: string;
  counts: { new: number; add: number; trim: number; exit: number };
  lists: {
    top_new: DiffItem[];
    top_add: DiffItem[];
    top_trim: DiffItem[];
    top_exit: DiffItem[];
  };
};

function formatNum(n: number): string {
  return n >= 0 ? n.toLocaleString() : `-${Math.abs(n).toLocaleString()}`;
}

function formatWeight(w: number): string {
  return `${(w * 100).toFixed(2)}%`;
}

function TableBlock({
  title,
  items,
}: {
  title: string;
  items: DiffItem[];
}) {
  if (items.length === 0) {
    return (
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-2">{title}</h2>
        <p className="text-sm opacity-70">No items.</p>
      </section>
    );
  }
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold mb-2">{title}</h2>
      <div className="overflow-x-auto rounded border border-[#1F2937]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#111827] border-b border-[#1F2937]">
              <th className="text-left p-2">Issuer</th>
              <th className="text-right p-2">Value Δ</th>
              <th className="text-right p-2">Weight Δ</th>
              <th className="text-right p-2">Shares Δ</th>
              <th className="text-right p-2">Value Now</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row, i) => (
              <tr key={i} className="border-b border-[#1F2937] last:border-0">
                <td className="p-2">{row.issuer}</td>
                <td className="text-right p-2">{formatNum(row.value_delta)}</td>
                <td className="text-right p-2">{formatWeight(row.weight_delta)}</td>
                <td className="text-right p-2">{formatNum(row.shares_delta)}</td>
                <td className="text-right p-2">{formatNum(row.value_now)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default async function MoversPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const filePath = path.join(DATA_DIR, `${slug}.json`);

  let payload: DiffPayload | null = null;
  try {
    if (fs.existsSync(filePath)) {
      const raw = fs.readFileSync(filePath, "utf-8");
      payload = JSON.parse(raw) as DiffPayload;
    }
  } catch {
    payload = null;
  }

  if (!payload || !payload.quarter_prev) {
    return (
      <main className="mx-auto max-w-5xl p-6">
        <div className="mb-6">
          <Link href={`/manager/${slug}`} className="text-sm underline text-[#4ADE80]">
            ← Manager
          </Link>
        </div>
        <h1 className="text-xl font-semibold">Top Movers</h1>
        <p className="mt-4 text-[#F9FAFB] opacity-80">
          Not enough history yet.
        </p>
        <p className="mt-2 text-sm opacity-60">
          Run the fetcher to generate history and diff for this manager.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <Link href={`/manager/${slug}`} className="text-sm underline text-[#4ADE80]">
          ← Manager
        </Link>
      </div>
      <h1 className="text-xl font-semibold">{payload.name}</h1>
      <p className="text-sm opacity-70 mt-1">
        {payload.quarter_now} vs {payload.quarter_prev}
        {payload.filing_date_now ? ` · Filed ${payload.filing_date_now}` : ""}
      </p>
      <p className="text-sm opacity-60 mt-1">
        NEW {payload.counts.new} · ADD {payload.counts.add} · TRIM {payload.counts.trim} · EXIT {payload.counts.exit}
      </p>

      <TableBlock title="New" items={payload.lists.top_new} />
      <TableBlock title="Add" items={payload.lists.top_add} />
      <TableBlock title="Trim" items={payload.lists.top_trim} />
      <TableBlock title="Exit" items={payload.lists.top_exit} />
    </main>
  );
}
