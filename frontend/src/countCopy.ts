// 件数唯一口径：该杆 active 占位数（一件衣物一个 active 段）。
// 角标件数、占位图段数、上杆校验在后端共用同一计数，前端不做任何 +/-1 换算。

export function countCaption(activeCount: number, limit: number | null): string {
  const limitText = limit == null ? "不限" : String(limit);
  const room = limit == null ? "不限" : (activeCount >= limit ? "已满" : "未满");
  return `件数 ${activeCount} / 上限 ${limitText} / ${room}`;
}
