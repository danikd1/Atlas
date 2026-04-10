interface SummaryPanelProps {
  text: string;
}

export function SummaryPanel({ text }: SummaryPanelProps) {
  return (
    <div className="bg-amber-50 border border-amber-200 border-t-0 rounded-b-lg px-5 py-3 -mt-1">
      <p className="text-xs font-medium text-amber-700 mb-1">AI-резюме</p>
      <p className="text-sm text-gray-700 leading-relaxed">{text}</p>
    </div>
  );
}
