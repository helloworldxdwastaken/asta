import { IconCheck } from "../../lib/icons";

interface ToolIndicatorProps {
  activeTools: string[];
  completedTools: string[];
}

export default function ToolIndicator({ activeTools, completedTools }: ToolIndicatorProps) {
  return (
    <>
      {/* Active tool pills (animated) */}
      {activeTools.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {activeTools.map(tool => (
            <span key={tool} className="inline-flex items-center gap-1.5 rounded-full bg-accent/[.1] border border-accent/[.15] px-3 py-1 text-11 font-medium text-accent animate-fade-in">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              {tool}
            </span>
          ))}
        </div>
      )}
      {/* Completed tool pills */}
      {completedTools.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2.5">
          {completedTools.map(tool => (
            <span key={tool} className="inline-flex items-center gap-1.5 rounded-full bg-white/[.04] border border-separator px-2.5 py-1 text-11 text-label-secondary">
              <IconCheck size={10} className="text-success" />
              {tool}
            </span>
          ))}
        </div>
      )}
    </>
  );
}
