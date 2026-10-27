import {expect,it} from 'vitest';
import {integerTicks,gradeColor,gradeShares,moneyLabel,orderedTrend,labelLines} from './chart-data';
it('uses one integer scale for all department bars and handles small/zero counts',()=>{
 expect(integerTicks(38)).toEqual([0,10,20,30,40]);expect(integerTicks(1)).toEqual([0,1]);expect(integerTicks(0)).toEqual([0,1]);expect(integerTicks(7).every(Number.isInteger)).toBe(true);
});
it('keeps grade colors stable and rounds shares to exactly 100 percent',()=>{
 const rows=[{name:'G1',count:1},{name:'G2',count:1},{name:'G3',count:1}];const shares=gradeShares(rows);
 expect(shares.reduce((sum,row)=>sum+row.tenths,0)).toBe(1000);expect(shares.map(row=>row.percent)).toEqual(['33.4','33.3','33.3']);expect(gradeColor('G2')).toBe(gradeColor([...rows].reverse()[1].name));expect(gradeShares([{name:'G1',count:0}])).toEqual([]);
});
it('uses exact decimal text for money labels while sorting real monthly points',()=>{
 expect(moneyLabel('1234567890.01')).toBe('1,234,567,890.01');expect(moneyLabel('0.00')).toBe('0.00');
 const data=[{month:'2026-10',amount:'0.00'},{month:'2026-09',amount:'12.34'}];expect(orderedTrend(data).map(row=>row.month)).toEqual(['2026-09','2026-10']);expect(data[0].month).toBe('2026-10');
 expect(()=>orderedTrend([{month:'2026-08',amount:'1.00'},{month:'2026-10',amount:'2.00'}])).toThrow();
});
it('wraps long department labels without removing characters',()=>{
 const label='研发中心及基础设施平台支持部门';expect(labelLines(label,7).join('')).toBe(label);expect(labelLines(label,7).length).toBeGreaterThan(1);
});

it('accepts the preceding year in an allowed early-2000 six-month query',()=>{
 const months=['1999-08','1999-09','1999-10','1999-11','1999-12','2000-01'];expect(orderedTrend(months.map(month=>({month,amount:'0.00'}))).map(row=>row.month)).toEqual(months);
});
