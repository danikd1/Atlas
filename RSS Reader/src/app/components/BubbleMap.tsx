import { useEffect, useRef, useState } from "react";
import * as d3 from "d3-hierarchy";

export interface TopicBubble {
  id: number;
  name: string;
  keywords?: string;
  description?: string;
  article_count: number;
}

interface BubbleMapProps {
  topics: TopicBubble[];
  selectedId: number | null;
  onSelect: (topic: TopicBubble) => void;
}

const stripQuotes = (s: string) => s.replace(/^[«"']+|[»"']+$/g, "").trim();

const COLORS = [
  "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444",
  "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#6366f1",
];

export function BubbleMap({ topics, selectedId, onSelect }: BubbleMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [bubbles, setBubbles] = useState<{
    topic: TopicBubble;
    color: string;
    x: number;
    y: number;
    r: number;
  }[]>([]);
  const [tooltip, setTooltip] = useState<{
    topic: TopicBubble;
    x: number;
    y: number;
  } | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!topics.length || !size.w || !size.h) return;

    const root = d3
      .hierarchy<any>({ children: topics })
      .sum((d: any) => Math.max(1, d.article_count ?? 1));

    d3.pack<any>().size([size.w - 16, size.h - 16]).padding(6)(root as any);

    setBubbles(
      (root as any).leaves().map((node: any, i: number) => ({
        topic: node.data as TopicBubble,
        color: COLORS[i % COLORS.length],
        x: node.x,
        y: node.y,
        r: node.r,
      }))
    );
  }, [topics, size]);

  return (
    <div ref={containerRef} className="relative w-full h-full select-none">
      <svg width={size.w} height={size.h} className="absolute inset-0">
        <defs>
          {bubbles.map(({ topic, x, y, r }) => (
            <clipPath key={`clip-${topic.id}`} id={`clip-${topic.id}`}>
              <circle cx={x + 8} cy={y + 8} r={r - 4} />
            </clipPath>
          ))}
        </defs>

        {bubbles.map(({ topic, color, x, y, r }) => {
          const isSelected = topic.id === selectedId;
          const cx = x + 8;
          const cy = y + 8;
          const showText = r > 40;
          // Шрифт пропорционален радиусу
          const fontSize = r < 60 ? Math.max(9, r / 6) : Math.max(10, Math.min(14, r / 6));
          // Внутренний квадрат вписанный в круг
          const inner = r * Math.SQRT2 * 0.8;
          const displayName = stripQuotes(topic.name);

          return (
            <g
              key={topic.id}
              onClick={() => onSelect(topic)}
              onMouseEnter={(e) => setTooltip({ topic, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
              className="cursor-pointer"
            >
              {/* Тень */}
              <circle cx={cx + 2} cy={cy + 3} r={r} fill={color} opacity={0.12} />
              {/* Основной круг */}
              <circle
                cx={cx} cy={cy} r={r}
                fill={color}
                opacity={isSelected ? 1 : 0.8}
                stroke="white"
                strokeWidth={isSelected ? 3 : 0}
              />
              {/* Текст через foreignObject — CSS сам переносит слова */}
              {showText && (
                <foreignObject
                  x={cx - inner / 2}
                  y={cy - inner / 2}
                  width={inner}
                  height={inner}
                  clipPath={`url(#clip-${topic.id})`}
                  style={{ pointerEvents: "none" }}
                >
                  <div
                    style={{
                      width: "100%",
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "6px",
                      boxSizing: "border-box",
                    }}
                  >
                    <p
                      style={{
                        textAlign: "center",
                        color: "white",
                        fontSize: `${fontSize}px`,
                        fontWeight: 600,
                        lineHeight: 1.3,
                        wordBreak: "break-word",
                        overflow: "hidden",
                        display: "-webkit-box",
                        WebkitBoxOrient: "vertical",
                        WebkitLineClamp: 4,
                        margin: 0,
                      }}
                    >
                      {displayName}
                    </p>
                  </div>
                </foreignObject>
              )}
            </g>
          );
        })}
      </svg>

      {/* Тултип */}
      {tooltip && (
        <div
          className="fixed z-50 bg-gray-900 text-white text-xs rounded-xl px-3 py-2.5 shadow-xl pointer-events-none max-w-[240px]"
          style={{
            left: Math.min(tooltip.x + 14, window.innerWidth - 260),
            top: tooltip.y + 140 > window.innerHeight
              ? Math.max(8, tooltip.y - 160)
              : tooltip.y - 40,
          }}
        >
          <p className="font-semibold text-sm mb-1 leading-snug">{stripQuotes(tooltip.topic.name)}</p>
          <p className="text-gray-400 mb-1.5">{tooltip.topic.article_count} статей</p>
          {(tooltip.topic.description || tooltip.topic.keywords) && (
            <p className="text-gray-300 leading-relaxed">
              {tooltip.topic.description
                ? tooltip.topic.description
                : tooltip.topic.keywords!.split(",").slice(0, 6).map(k => k.trim()).join(" · ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
