import {expect,it} from 'vitest';
import {parseDateText,formatChineseDate,calendarDays,dateValue} from './chinese-date';
it('keeps ISO transport separate from Chinese display without timezone conversion',()=>{expect(formatChineseDate('2026-10-27')).toBe('2026年10月27日');expect(parseDateText('2026年10月27日')).toBe('2026-10-27');expect(parseDateText('2026-01-01')).toBe('2026-01-01');expect(formatChineseDate('')).toBe('');});
it('rejects invalid calendar dates rather than rolling them into another month',()=>{expect(parseDateText('2025-02-29')).toBeNull();expect(parseDateText('2024年2月29日')).toBe('2024-02-29');expect(parseDateText('2026-13-01')).toBeNull();expect(parseDateText('2026-04-31')).toBeNull();expect(parseDateText('0000-01-01')).toBeNull();});
it('lays out a Chinese Monday-first calendar and preserves the exact selected date',()=>{const cells=calendarDays(2026,10);expect(cells.slice(0,5)).toEqual([null,null,null,1,2]);expect(cells.filter(day=>day!==null)).toHaveLength(31);expect(dateValue(2026,1,2)).toBe('2026-01-02');});
it('supports natural Chinese attendance rule dates while preserving existing padded displays and ISO values',()=>{
 expect(formatChineseDate('2026-01-02',false)).toBe('2026年1月2日');
 expect(formatChineseDate('2026-10-28',false)).toBe('2026年10月28日');
 expect(parseDateText('2026年1月2日')).toBe('2026-01-02');
 expect(formatChineseDate('2026-01-02')).toBe('2026年01月02日');
});
