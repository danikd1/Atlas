import { HelpCircle } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

interface FeatureHintProps {
  title: string;
  description: string;
  bullets?: string[];
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
}

export function FeatureHint({
  title,
  description,
  bullets,
  side = "bottom",
  align = "end",
}: FeatureHintProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className="p-1 rounded-md text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors flex-shrink-0"
          aria-label={`Что такое ${title}?`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent side={side} align={align} className="w-72 text-sm">
        <p className="font-semibold text-gray-900 mb-1">{title}</p>
        <p className="text-gray-600 leading-relaxed text-xs">{description}</p>
        {bullets && bullets.length > 0 && (
          <ul className="mt-2 space-y-1">
            {bullets.map((b, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-gray-500">
                <span className="mt-0.5 w-1 h-1 rounded-full bg-blue-400 flex-shrink-0" />
                {b}
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
