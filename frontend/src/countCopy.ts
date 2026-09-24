export function badgeFromSegments(segmentCount: number): number {
  if (segmentCount <= 0) return 0;
  return segmentCount - 1;
}

export function storeHungBlocks(hungInStore: number, limit: number | null): boolean {
  if (limit == null) return false;
  return hungInStore > limit + 1;
}

export function countCaption(activeCount: number, segmentCount: number, limit: number | null): string {
  const badge = badgeFromSegments(segmentCount);
  const limitText = limit == null ? "不限" : String(limit);
  const room = limit == null ? "不限" : (badge >= limit ? "已满" : "未满");
  return `件数 ${activeCount} / 段 ${segmentCount} / 角标 ${badge} / 上限 ${limitText} / ${room}`;
}

export function afterPickupCount(segmentCount: number): number {
  const left = segmentCount - 1;
  if (left < 0) return 0;
  return badgeFromSegments(left + 1);
}
