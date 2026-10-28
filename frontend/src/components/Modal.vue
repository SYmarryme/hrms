<script setup lang="ts">
import {ref,computed,onMounted,onBeforeUnmount,useId,inject,watch} from 'vue';
import {useRoute} from 'vue-router';
import {pageActivityKey} from '../page-activity';
import {workspace,markDirty,verifySession} from '../workspace';
import {confirmAction,lockBackground,unlockBackground} from '../modal';
const props=withDefaults(defineProps<{title:string;returnFocus?:HTMLElement|null;busy?:boolean;error?:string;scope?:string;trackChanges?:boolean;concealed?:boolean;wide?:boolean;dismissible?:boolean}>(),{busy:false,error:'',scope:'editor',trackChanges:true,concealed:false,wide:false,dismissible:true});
const emit=defineEmits<{close:[];retry:[]}>();
const route=useRoute(),dialog=ref<HTMLDialogElement|null>(null),changed=ref(false),titleId=useId();
const pageActivity=inject(pageActivityKey,null),pagePath=pageActivity?.path||route.path;
let mounted=false,shown=false;
const concealed=computed(()=>workspace.cover||props.concealed);
let opener:HTMLElement|null=null,closing=false;
function dirty(event:Event){const target=event.target as HTMLElement;if(props.trackChanges&&!target.closest('.search-row')){changed.value=true;markDirty(pagePath,true,props.scope);}}
async function requestClose(){
 if(!props.dismissible||props.busy||closing)return;closing=true;
 try{if(changed.value&&!await confirmAction({title:'放弃未保存修改',message:'当前输入尚未保存，确定放弃这些修改吗？',confirmLabel:'放弃修改',cancelLabel:'继续编辑',danger:true}))return;
 emit('close');}finally{closing=false;}
}
function cancelClick(event:MouseEvent){if((event.target as HTMLElement).closest('[data-modal-cancel]')){event.preventDefault();event.stopImmediatePropagation();void requestClose();}}
function guardSubmit(event:Event){if(props.busy||concealed.value){event.preventDefault();event.stopImmediatePropagation();}}
function trapFocus(event:KeyboardEvent){
 event.stopPropagation();if(event.key!=='Tab'||!dialog.value)return;
 const controls=[...dialog.value.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]')].filter(el=>el.getClientRects().length&&!el.matches(':disabled')&&!el.closest('[hidden],[inert]'));
 const first=controls[0],last=controls.at(-1),active=document.activeElement;
 if(!first){event.preventDefault();dialog.value.focus();return;}
 if(!controls.includes(active as HTMLElement)||event.shiftKey&&active===first||!event.shiftKey&&active===last){event.preventDefault();(event.shiftKey?last:first)?.focus();}
}
async function retry(){if(workspace.cover)await verifySession();emit('retry');}
function show(){if(!mounted||shown||pageActivity?.active.value===false)return;opener=props.returnFocus||(document.activeElement instanceof HTMLElement?document.activeElement:null);lockBackground();dialog.value?.showModal();shown=true;}
function hide(){if(!shown)return;dialog.value?.close();unlockBackground();shown=false;if(opener?.isConnected)opener.focus({preventScroll:true});}
onMounted(()=>{mounted=true;show();});
watch(()=>pageActivity?.active.value,active=>{if(active===false)hide();else show();},{flush:'sync'});
onBeforeUnmount(()=>{mounted=false;hide();if(props.trackChanges)markDirty(pagePath,false,props.scope);});
</script>
<template><Teleport to="body"><dialog ref="dialog" :aria-labelledby="titleId" :class="['business-modal',{'modal-wide':wide}]" @cancel.prevent="requestClose" tabindex="-1" @keydown="trapFocus" @click.capture="cancelClick" @submit.capture="guardSubmit" @input="dirty" @change="dirty">
 <div v-if="concealed" class="modal-verification" role="status">正在确认访问权限，请稍候。<button @click="retry">重试</button></div>
 <div v-show="!concealed" class="modal-layout"><header class="modal-heading"><h2 :id="titleId">{{title}}</h2><button v-if="dismissible" type="button" class="modal-close" aria-label="关闭弹窗" :disabled="busy" @click="requestClose">×</button></header>
 <div class="modal-content"><p v-if="error" class="error feedback" role="alert">{{error}}</p><fieldset class="modal-fields" :disabled="busy"><slot/></fieldset></div><footer v-if="$slots.footer||!trackChanges&&dismissible" class="modal-footer"><slot name="footer"><button type="button" class="secondary" :disabled="busy" data-modal-cancel>关闭</button></slot></footer></div>
</dialog></Teleport></template>
