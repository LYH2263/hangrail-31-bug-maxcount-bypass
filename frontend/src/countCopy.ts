export function countCaption(activeCount: number, limit: number | null): string {
  const limitText = limit == null ? "不限" : String(limit);
  const room = limit == null ? "" : activeCount >= limit ? " · 已满" : "";
  return `件数 ${activeCount} / 上限 ${limitText}${room}`;
}
