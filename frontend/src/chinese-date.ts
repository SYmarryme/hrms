export const dateValue=(year:number,month:number,day:number)=>`${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
export function daysInMonth(year:number,month:number){return [31,year%4===0&&(year%100!==0||year%400===0)?29:28,31,30,31,30,31,31,30,31,30,31][month-1]||0;}
export function parseDateText(value:string):string|null{
 const parts=/^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value.trim())||/^(\d{4})年(\d{1,2})月(\d{1,2})日$/.exec(value.trim());
 if(!parts)return null;const [year,month,day]=parts.slice(1).map(Number);return year>=1&&year<=9999&&month>=1&&month<=12&&day>=1&&day<=daysInMonth(year,month)?dateValue(year,month,day):null;
}
export function formatChineseDate(value:string,padded=true){const valid=parseDateText(value);return valid?valid.slice(0,4)+'年'+(padded?valid.slice(5,7):Number(valid.slice(5,7)))+'月'+(padded?valid.slice(8,10):Number(valid.slice(8,10)))+'日':'';}
export function calendarDays(year:number,month:number):(number|null)[]{const first=new Date(0);first.setUTCFullYear(year,month-1,1);const offset=(first.getUTCDay()+6)%7;return [...Array<null>(offset).fill(null),...Array.from({length:daysInMonth(year,month)},(_,i)=>i+1)];}
