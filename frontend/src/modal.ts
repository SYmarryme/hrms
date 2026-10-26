import {reactive,ref} from 'vue';
export const modalCount=ref(0);
let previousOverflow='',previousInert=false;
let background:HTMLElement|null=null;
export function lockBackground(){if(modalCount.value++===0){previousOverflow=document.documentElement.style.overflow;document.documentElement.style.overflow='hidden';background=document.getElementById('app');previousInert=background?.inert??false;if(background)background.inert=true;}}
export function unlockBackground(){modalCount.value=Math.max(0,modalCount.value-1);if(!modalCount.value){document.documentElement.style.overflow=previousOverflow;if(background)background.inert=previousInert;background=null;}}
export interface Confirmation {title:string;message:string;confirmLabel?:string;cancelLabel?:string;danger?:boolean}
export const confirmation=reactive({current:null as Confirmation|null,busy:false,error:''});
let resolveConfirmation:((accepted:boolean)=>void)|null=null,operation:(()=>Promise<void>)|null=null,generation=0;
export function finishConfirmation(accepted=false){generation++;const resolve=resolveConfirmation;resolveConfirmation=null;operation=null;confirmation.current=null;confirmation.busy=false;confirmation.error='';resolve?.(accepted);}
export function confirmAction(options:Confirmation):Promise<boolean>{
 if(resolveConfirmation)return Promise.resolve(false);
 confirmation.current=options;confirmation.error='';return new Promise(resolve=>{resolveConfirmation=resolve;});
}
export function confirmOperation(options:Confirmation,action:()=>Promise<void>):Promise<boolean>{
 if(resolveConfirmation)return Promise.resolve(false);
 const result=confirmAction(options);operation=action;return result;
}
export async function acceptConfirmation(){
 if(confirmation.busy||!confirmation.current)return;
 if(!operation){finishConfirmation(true);return;}
 const mine=generation;confirmation.busy=true;confirmation.error='';
 try{await operation();if(mine===generation)finishConfirmation(true);}
 catch(error){if(mine===generation)confirmation.error=error instanceof Error?error.message:'操作未完成，请重试';}
 finally{if(mine===generation)confirmation.busy=false;}
}
