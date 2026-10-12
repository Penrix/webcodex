(function () {
  'use strict';
  function messageIdentity(value) {
    const ids = [...new Set((value || '').trim().split(/\s+/).filter(Boolean))];
    if (ids.length !== 1) throw new Error('Message identity missing or ambiguous; stopped');
    return ids[0];
  }
  function completedEnvelope(message, baseline, requestId) {
    if (!message.complete || message.role !== 'assistant' || !message.id || baseline.has(message.id)) return null;
    if (message.codes.length !== 1) return null;
    try {
      const envelope = JSON.parse(message.codes[0]);
      if (Object.keys(envelope).sort().join(',') !== 'action,request_id' || envelope.request_id !== requestId) return null;
      if (!envelope.action || !['discover','call','final'].includes(envelope.action.kind)) return null;
      return envelope;
    } catch { return null; }
  }
  const api = {completedEnvelope, messageIdentity};
  if (typeof module !== 'undefined') module.exports = api;
  else globalThis.WebCodexProtocol = api;
})();
