/* 分步界面。所有药品、回答、录音和县区均来自原业务；不生成模拟结果，不新增AI审核。 */
(function () {
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var state={view:'photo',product:null,confirmed:false,response:null,pages:[],page:0,raw:'',lastFocus:null,toastTimer:0,resizeTimer:0};
  var views={photo:['photoSection','photoActions'],identity:['identitySection','identityActions'],question:['questionSection','questionActions'],scanning:['waitingSection','waitingActions'],asking:['waitingSection','waitingActions'],unmatched:['unmatchedSection','unmatchedActions'],answer:['answerSection','answerActions']};
  function text(node,value){value=String(value||'');if(node&&node.textContent!==value)node.textContent=value;}
  function hidden(node,value){if(node&&node.hidden!==value)node.hidden=value;}
  function disabled(node,value){if(node.disabled!==value)node.disabled=value;}
  function escape(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function toast(message){clearTimeout(state.toastTimer);text($('flowToast'),message);hidden($('flowToast'),false);state.toastTimer=setTimeout(function(){hidden($('flowToast'),true);},3500);}
  function showDialog(id){var node=$(id);state.lastFocus=document.activeElement;if(typeof node.showModal==='function')node.showModal();else node.setAttribute('open','');}
  function closeDialog(node){if(!node)return;if(typeof node.close==='function')node.close();else node.removeAttribute('open');if(state.lastFocus&&state.lastFocus.isConnected)state.lastFocus.focus();}
  function closeAll(){document.querySelectorAll('dialog[open]').forEach(function(node){closeDialog(node);});}
  function updateProducts(){
    var p=state.product;if(!p)return;
    text($('recognizedDrug'),p.药名);text($('recognizedMeta'),p.规格);
    document.querySelectorAll('[data-product-summary]').forEach(function(node){
      var compact=String(p.规格||'').split(/[（(]含/)[0]; // 复方成分明细仍完整保留在确认页、OCR与依据窗口。
      var html='<svg class="product-symbol" aria-hidden="true" viewBox="0 0 32 32"><rect x="8" y="3" width="16" height="5" rx="1" fill="currentColor"/><rect x="6" y="10" width="20" height="19" rx="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 14v11m-5-5h10" stroke="currentColor" stroke-width="3"/></svg><div><div class="medicine-name">'+escape(p.药名)+'</div><div class="medicine-spec">'+escape(compact)+'</div></div>';
      if(node.innerHTML!==html)node.innerHTML=html;
    });
  }
  function setView(view){
    if(!views[view])return;
    var changed=state.view!==view;state.view=view;$('flowApp').dataset.flow=view;
    var panel=views[view][0],actions=views[view][1];
    ['photoSection','identitySection','questionSection','waitingSection','unmatchedSection','answerSection'].forEach(function(id){hidden($(id),id!==panel);});
    ['photoActions','identityActions','questionActions','waitingActions','unmatchedActions','answerActions'].forEach(function(id){hidden($(id),id!==actions);});
    var step=['photo','scanning','identity','unmatched'].indexOf(view)>=0?1:view==='question'?2:3;
    document.querySelectorAll('.steps li').forEach(function(li){var n=Number(li.dataset.step);li.classList.toggle('current',n===step);li.classList.toggle('done',n<step);if(n===step)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});
    if(view==='scanning'||view==='asking'){
      text($('waitTitle'),view==='scanning'?'正在识别药盒…':'正在查看说明书…');
      $('waitMessage').innerHTML=view==='scanning'?'正在读取药名和规格，<br>请稍等一下。':'正在按这盒药的资料回答，<br>请稍等一下。';
      text($('waitPill'),view==='scanning'?'识别中':'回答尚未返回，暂不播报');
      text($('waitQuestion'),'您问：'+lastQuestion);hidden($('waitQuestion'),view!=='asking');
      text($('cancelCurrent'),view==='scanning'?'取消，重新拍':'取消，返回修改');
    }
    updateProducts();syncQuestion();syncAudio();
    if(changed){$(panel).scrollTop=0;$(panel).focus({preventScroll:true});}
    if(view==='answer')paginate(false);
  }
  function questionText(){var typed=($('askInput').value||'').trim(),spoken=($('voiceText').textContent||'').trim();if(/^[（(]?没听清/.test(spoken))spoken='';return lastInputFrom==='voice'?(spoken||typed):(typed||spoken);}
  function syncQuestion(){
    var q=questionText(),recording=typeof Recorder!=='undefined'&&Recorder.isRecording();
    text($('questionPreview'),q||'说完的话会显示在这里');$('questionPreview').classList.toggle('empty',!q);
    var busy=state.view==='asking';disabled($('btnAsk'),busy||!q||voiceBusy||recording||ocrBusy||!state.confirmed);
    $('btnAsk').classList.toggle('is-thinking',busy);text($('btnAsk').querySelector('.action-label'),busy?'正在查看说明书…':'开始问药');
    $('btnMic').classList.toggle('recording',recording&&/正在录音/.test($('voiceStatus').textContent));
    $('btnMic').setAttribute('aria-pressed',recording?'true':'false');text($('btnMic').querySelector('.action-label'),recording?'正在听您说':'按住说话');
    hidden($('voiceStatus'),/^按住按钮，说完松手$/.test($('voiceStatus').textContent));
    text($('languageLabel'),$('asrProvider').value==='baidu'?'普通话':'桂柳话 / 普通话（试用）');disabled($('openLanguage'),recording||voiceBusy);
  }
  function syncAudio(){
    var dialect=$('btnSpeak').style.display!=='none'&&!!voiceFile;
    $('voiceControls').classList.toggle('single-voice',!dialect);
    if(state.view==='answer'){
      var notice=$('askStatus').textContent||'';
      var status=state.response&&(state.response.answer_status!=='answered'||state.response.refuse_kind)?'这次先不讲服法':'说明书讲解';
      if(/完整禁忌使用普通话/.test(notice))status='完整禁忌使用普通话';
      text($('answerLabel'),status);$('answerLabel').classList.toggle('refused',!!state.response&&(state.response.answer_status!=='answered'||!!state.response.refuse_kind));
      hidden($('openEvidence'),!$('citationBox').textContent.trim());
    }
  }
  function syncLocation(){
    var code=typeof regionCode==='string'?regionCode:'',loc=typeof locationState==='string'?locationState:'unavailable',choice=typeof locationChoice==='object'?locationChoice:null;
    var full=$('locationStatus').textContent||'',title='暂未确认县区',summary='可更换县区，也可以直接拍照问药。',badge='未确认';
    if(code&&(loc==='manual'||loc==='confirmed')){
      var match=full.match(/^(?:人工校准|您已确认所在县区)：([^。]+)/);title=match?match[1]:'已确认所在县区';badge=loc==='manual'?'人工校准':'已确认';summary='仅用于统计；换地方请重新选择。';
    }else if(choice&&loc==='pending_confirmation'){
      title=choice.name;badge='待确认';summary=choice.kind==='saved'?'上次记住的县区，请您再次确认。':'设备建议可能不准，请您核对。';
    }else if(!$('manualLocationPanel').hidden){title='选择实际所在县区';badge='待选择';summary='确认前不计入统计，不影响问药。';}
    else if(loc==='requesting'){title='正在获取设备建议…';badge='获取中';summary='不提供位置，也可以拍照和问药。';}
    else if(loc==='rejected_location'){title='暂不提供县区';badge='未提供';summary='可以正常拍照、提问和听乡音。';}
    else if(loc==='denied')summary='未获定位许可，可以选择县区或直接问药。';
    else if(loc==='timeout')summary='设备定位超时，可以选择县区或直接问药。';
    else if(loc==='outside')summary='设备建议不在已支持区域，可以直接问药。';
    else if(loc==='unstable'||(typeof locationConflict!=='undefined'&&locationConflict))summary='设备建议不一致，请选择实际县区。';
    text($('locationCounty'),title);text($('locationSummary'),summary);text($('locationBadge'),badge);
    text($('countyQuickLabel'),badge==='待确认'?'建议：'+title+' · 待确认':badge==='已确认'||badge==='人工校准'?title+' · '+badge:title);
    $('countyQuickLabel').title=summary;text($('confirmLocation'),'位置正确');text($('rejectLocation'),'更换县区');
    $('confirmLocation').parentNode.classList.toggle('single-action',$('confirmLocation').hidden);
  }
  function resetQuestion(keepQuestion){
    newTask();stopPlayback();if(typeof Recorder.cancel==='function')Recorder.cancel();voiceBusy=false;answer.textContent='';text($('answerPage'),'');clearCitation();state.response=null;state.raw='';state.pages=[];state.page=0;
    if(!keepQuestion){lastQuestion='';lastInputFrom='text';voiceText.textContent='';askInput.value='';text($('voiceStatus'),'按住按钮，说完松手');}
    text($('askStatus'),'');setView('question');
  }
  function changeDrug(){
    closeAll();newTask();resetForNewTask();ocrBusy=false;state.product=null;state.confirmed=false;state.response=null;state.pages=[];state.raw='';state.page=0;
    result.textContent='';text($('answerPage'),'');if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl='';}preview.removeAttribute('src');preview.style.display='none';fileInput.value='';text($('voiceStatus'),'按住按钮，说完松手');text($('askStatus'),'');setView('photo');
  }
  function openCamera(){fileInput.setAttribute('capture','environment');fileInput.click();}
  function openGallery(){fileInput.removeAttribute('capture');fileInput.click();}
  function ocrFinished(data){
    if(data&&data.ok&&data.product&&data.product.药名&&data.product.规格){state.product=data.product;state.confirmed=false;setView('identity');}
    else{state.product=null;state.confirmed=false;text($('unmatchedTitle'),data&&data.ok?'还没匹配到具体药品':'这张还没读成功');text($('unmatchedMessage'),data&&data.ok?'请把正面的药名、规格拍清楚；认准具体产品后再问药。':'可以重新拍一张，或从已有照片选择。');setView('unmatched');}
  }
  function answerReturned(data){state.response=data;state.raw=answer.textContent;state.pages=[];state.page=0;text($('answerPage'),state.raw);text($('askedQuestion'),'您问：'+lastQuestion);setView('answer');}
  function answerFailed(){if(state.view==='asking')setView('question');}
  function sentenceBlocks(raw){
    var blocks=raw.match(/[\s\S]*?[。！？；](?:[”’」』]*)|[\s\S]+$/g)||[raw],joined=[];
    blocks.forEach(function(block){if(joined.length&&/^\s*(?:除非|但是|但|否则|except\b|unless\b)/i.test(block))joined[joined.length-1]+=block;else joined.push(block);});
    return joined;
  }
  function fitText(value){var node=$('answerPage');node.textContent=value;return node.scrollHeight<=node.clientHeight+1;}
  function paginate(preserve){
    if(state.view!=='answer'||!answer.textContent.trim())return;
    var node=$('answerPage'),raw=answer.textContent,anchor=preserve?state.pages.slice(0,state.page).join('').length:0;
    node.classList.toggle('long',raw.length>100);$('answerActions').classList.toggle('long-answer-actions',raw.length>100);
    hidden($('answerPager'),true);hidden($('pageScrollHint'),true);
    if(fitText(raw)){state.pages=[raw];state.raw=raw;state.page=0;renderPage();return;}
    hidden($('answerPager'),false);
    var pages=[],current='';
    sentenceBlocks(raw).forEach(function(block){if(current&&!fitText(current+block)){pages.push(current);current=block;}else current+=block;});
    if(current)pages.push(current);if(!pages.length)pages=[raw];
    if(pages.join('')!==raw)pages=[raw]; // 禁止遗漏、重排或改写回答文字。
    state.pages=pages;state.raw=raw;state.page=0;
    var offset=0;for(var i=0;i<pages.length;i++){if(offset<=anchor)state.page=i;offset+=pages[i].length;if(offset>anchor)break;}
    // 单页移除翻页区后空间更宽裕，不再增加无意义的空页。
    hidden($('answerPager'),pages.length===1);renderPage();
  }
  function renderPage(){
    text($('answerPage'),state.pages[state.page]||state.raw);$('answerPage').scrollTop=0;
    text($('answerPageCount'),'第 '+(state.page+1)+' / '+state.pages.length+' 页');disabled($('answerPrev'),state.page===0);disabled($('answerNext'),state.page>=state.pages.length-1);
    requestAnimationFrame(function(){var node=$('answerPage'),overflow=node.scrollHeight>node.clientHeight+2;hidden($('pageScrollHint'),!overflow);});
  }
  // 在原业务已完成任务编号检查后接收真实结果；这里只控制展示。
  window.XYStepUI={ocrFinished:ocrFinished,askStarted:function(){setView('asking');},answerReturned:answerReturned,answerFailed:answerFailed};
  $('btnPhoto').onclick=openCamera;$('cameraTarget').onclick=function(){$('btnPhoto').click();};$('btnGallery').onclick=openGallery;
  fileInput.addEventListener('change',function(){if(!fileInput.files[0])return;closeAll();state.product=null;state.confirmed=false;state.response=null;state.pages=[];state.raw='';setView('scanning');});
  $('confirmProduct').onclick=function(){if(state.product&&!ocrBusy&&ocrWords){state.confirmed=true;text($('askStatus'),'');setView('question');}};
  ['wrongProduct','changeDrugQuestion','changeDrugAnswer','retryPhoto'].forEach(function(id){$(id).onclick=changeDrug;});
  $('retryGallery').onclick=function(){changeDrug();openGallery();};
  $('continueQuestion').onclick=function(){resetQuestion(false);};
  $('cancelCurrent').onclick=function(){if(state.view==='scanning')changeDrug();else resetQuestion(true);};
  $('openTyping').onclick=function(){hidden($('typingError'),true);showDialog('typingDialog');setTimeout(function(){askInput.focus();},0);};
  askInput.addEventListener('input',function(){hidden($('typingError'),true);syncQuestion();});
  $('saveQuestion').onclick=function(){if(!askInput.value.trim()){hidden($('typingError'),false);askInput.focus();return;}if(voiceBusy||Recorder.isRecording()){newTask();Recorder.cancel();voiceBusy=false;text($('voiceStatus'),'已改用打字问题');}lastInputFrom='text';closeDialog($('typingDialog'));text($('askStatus'),'');syncQuestion();};
  $('openLanguage').onclick=function(){showDialog('languageDialog');};$('asrProvider').addEventListener('change',syncQuestion);$('saveLanguage').onclick=function(){closeDialog($('languageDialog'));syncQuestion();};
  $('openLocation').onclick=function(){syncLocation();showDialog('locationDialog');};
  ['confirmLocation','applyManualLocation','skipLocation','cancelManualLocation'].forEach(function(id){$(id).addEventListener('click',function(){if(locationState==='confirmed'||locationState==='manual'||locationState==='rejected_location'){closeDialog($('locationDialog'));syncLocation();}});});
  $('openHelp').onclick=function(){showDialog('helpDialog');};
  ['openOcr','openOcrFailure'].forEach(function(id){$(id).onclick=function(){showDialog('ocrDialog');};});
  $('openEvidence').onclick=function(){var body=$('citeBody');if(body)body.hidden=false;showDialog('evidenceDialog');};
  document.querySelectorAll('[data-close-dialog]').forEach(function(button){button.onclick=function(){closeDialog(button.closest('dialog'));};});
  $('answerPrev').onclick=function(){if(state.page>0){state.page--;renderPage();}};$('answerNext').onclick=function(){if(state.page<state.pages.length-1){state.page++;renderPage();}};
  $('btnMic').addEventListener('keydown',function(e){if((e.key===' '||e.key==='Enter')&&!e.repeat){e.preventDefault();startVoice();}});
  $('btnMic').addEventListener('keyup',function(e){if(e.key===' '||e.key==='Enter'){e.preventDefault();sendVoice();}});
  [['voicePlayer','btnSpeak'],['player','btnSpeakPutong']].forEach(function(pair){var audio=$(pair[0]),button=$(pair[1]);audio.addEventListener('playing',function(){if(!audio.paused&&!audio.ended)button.classList.add('is-playing');});['pause','ended','error','waiting','stalled','emptied'].forEach(function(event){audio.addEventListener(event,function(){button.classList.remove('is-playing');});});});
  ['btnPhoto','btnGallery','btnAsk','btnSpeak','btnSpeakPutong'].forEach(function(id){$(id).addEventListener('click',function(){if(!this.disabled){this.classList.remove('motion-tap');void this.offsetWidth;this.classList.add('motion-tap');}});});
  askInput.addEventListener('focus',function(){$('openTyping').querySelector('.pen-art').classList.add('pen-active');});
  var observer=new MutationObserver(function(){
    syncQuestion();syncLocation();syncAudio();
    if(state.view==='scanning'&&!ocrBusy&&/^(?:识别失败|请求出错|照片没有读成功)/.test(result.textContent))ocrFinished(null);
  });
  ['voiceStatus','voiceText','askStatus','locationStatus','result','speakStatus'].forEach(function(id){observer.observe($(id),{childList:true,subtree:true});});
  ['confirmLocation','manualLocationPanel'].forEach(function(id){observer.observe($(id),{attributes:true,attributeFilter:['hidden']});});
  ['btnSpeak','btnSpeakPutong'].forEach(function(id){observer.observe($(id),{attributes:true,attributeFilter:['style']});});
  function resize(){clearTimeout(state.resizeTimer);state.resizeTimer=setTimeout(function(){paginate(true);},100);}
  window.addEventListener('resize',resize);if(window.visualViewport)window.visualViewport.addEventListener('resize',resize);
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(resize).observe(document.querySelector('.flow-footer'));
  syncLocation();setView('photo');
})();
