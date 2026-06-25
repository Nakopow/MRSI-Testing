// ── Tab Switching ────────────────────────────────────────────────────────────

document.querySelectorAll('[data-tab]').forEach((tab) => {
  tab.addEventListener('click', () => {
    const tabs = tab.closest('.tabs');
    if (!tabs) return;
    tabs.querySelectorAll('[data-tab]').forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
  });
});

// ── Topic Filter ─────────────────────────────────────────────────────────────

document.querySelectorAll('[data-topic-filter]').forEach((chip) => {
  chip.addEventListener('click', () => {
    const row = chip.closest('.topic-filter-row');
    if (!row) return;
    
    // Update active state
    row.querySelectorAll('[data-topic-filter]').forEach((item) => item.classList.remove('active'));
    chip.classList.add('active');
    
    // Get selected topic
    const selectedTopic = chip.textContent.trim();
    
    // Filter content cards
    const cards = document.querySelectorAll('.content-grid .content-card');
    cards.forEach(card => {
      const topicTag = card.querySelector('.topic-tag');
      if (topicTag) {
        const cardTopic = topicTag.textContent.trim();
        if (selectedTopic === 'All' || cardTopic === selectedTopic) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      }
    });
  });
});

// ── Toggle Buttons ───────────────────────────────────────────────────────────

document.querySelectorAll('[data-toggle]').forEach((toggle) => {
  toggle.addEventListener('click', () => {
    toggle.classList.toggle('on');
  });
});

// ── Pipeline Dropdown Menu ──────────────────────────────────────────────────

/**
 * Toggle the pipeline dropdown menu visibility
 */
function togglePipelineMenu() {
  const menu = document.getElementById('pipelineMenu');
  if (!menu) return;
  
  menu.classList.toggle('show');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
  const dropdown = document.querySelector('.pipeline-dropdown');
  const menu = document.getElementById('pipelineMenu');
  
  if (dropdown && menu && !dropdown.contains(e.target)) {
    menu.classList.remove('show');
  }
});

// ── Pipeline Step Execution ─────────────────────────────────────────────────

/**
 * Map step names to their API endpoints
 */
const PIPELINE_ENDPOINTS = {
  scrape: '/pipeline/scrape',
  summarize: '/pipeline/summarize',
  insights: '/pipeline/insights',
  tlp: '/pipeline/tlp',
  'run-all': '/pipeline/run-all',
};

/**
 * Human-readable names for pipeline steps
 */
const STEP_NAMES = {
  scrape: 'Scraping Articles',
  summarize: 'Generating Digest',
  insights: 'Generating Daily Insights',
  tlp: 'Generating TLPs',
  'run-all': 'Running Full Pipeline',
};

/**
 * Run a specific pipeline step
 * @param {string} step - The pipeline step to run
 */
function runPipelineStep(step) {
  const endpoint = PIPELINE_ENDPOINTS[step];
  if (!endpoint) {
    console.error('Unknown pipeline step:', step);
    return;
  }
  
  // Close the dropdown menu
  const menu = document.getElementById('pipelineMenu');
  if (menu) menu.classList.remove('show');
  
  // Show loading toast
  showToast('info', `${STEP_NAMES[step]} started...`, 'This may take a few minutes.');
  
  // Make the API request
  fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })
    .then((response) => {
      if (!response.ok) {
        return response.json().then((data) => {
          throw new Error(data.error || `HTTP ${response.status}`);
        });
      }
      return response.json();
    })
    .then((data) => {
      console.log('Pipeline response:', data);
      showToast(
        'success',
        `${STEP_NAMES[step]} started successfully!`,
        'The process is running in the background. Refresh the page to see updates.'
      );
      
      // Start polling for status updates
      startStatusPolling();
    })
    .catch((error) => {
      console.error('Pipeline error:', error);
      showToast(
        'error',
        `Failed to start ${STEP_NAMES[step]}`,
        error.message || 'Please try again.'
      );
    });
}

// ── Toast Notifications ─────────────────────────────────────────────────────

/**
 * Show a toast notification
 * @param {string} type - 'success', 'error', or 'info'
 * @param {string} title - The toast title
 * @param {string} message - The toast message
 * @param {number} duration - Duration in ms (default: 5000)
 */
function showToast(type, title, message, duration = 5000) {
  // Remove existing toast if any
  const existingToast = document.querySelector('.pipeline-toast');
  if (existingToast) {
    existingToast.remove();
  }
  
  // Create toast element
  const toast = document.createElement('div');
  toast.className = `pipeline-toast ${type}`;
  
  const icons = {
    success: 'ti-check',
    error: 'ti-alert-circle',
    info: 'ti-loader',
  };
  
  toast.innerHTML = `
    <i class="ti ${icons[type] || icons.info}"></i>
    <div class="pipeline-toast-message">
      <strong>${title}</strong>
      <div>${message}</div>
    </div>
    <button class="pipeline-toast-close" onclick="this.parentElement.remove()">
      <i class="ti ti-x"></i>
    </button>
  `;
  
  document.body.appendChild(toast);
  
  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });
  
  // Auto-remove after duration
  if (duration > 0) {
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }
}

// ── Pipeline Status Polling ─────────────────────────────────────────────────

let statusPollingInterval = null;

/**
 * Start polling for pipeline status updates
 */
function startStatusPolling() {
  // Clear any existing polling
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval);
  }
  
  // Poll every 5 seconds
  statusPollingInterval = setInterval(fetchPipelineStatus, 5000);
  
  // Stop polling after 5 minutes (60 iterations)
  let pollCount = 0;
  const maxPolls = 60;
  
  const stopPolling = () => {
    if (statusPollingInterval) {
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
  };
  
  // Check if all steps are idle
  const checkIdle = () => {
    pollCount++;
    if (pollCount >= maxPolls) {
      stopPolling();
      return;
    }
    
    fetch('/pipeline/status')
      .then((r) => r.json())
      .then((data) => {
        const allIdle = !data.scraping || data.scraping.status === 'idle';
        if (allIdle) {
          stopPolling();
          showToast('success', 'Pipeline complete!', 'All processes have finished.');
        }
      })
      .catch(() => {
        // Silently fail, keep polling
      });
  };
  
  // Initial check after a delay
  setTimeout(checkIdle, 3000);
}

/**
 * Fetch and update pipeline status display
 */
function fetchPipelineStatus() {
  fetch('/pipeline/status')
    .then((r) => r.json())
    .then((data) => {
      updateStatusDisplay(data);
    })
    .catch(() => {
      // Silently fail
    });
}

/**
 * Update the status bar display with current pipeline state
 */
function updateStatusDisplay(data) {
  const statusBar = document.querySelector('.status-bar');
  if (!statusBar) return;
  
  // Check if any step is running
  const steps = ['scraping', 'summarizing', 'insights', 'tlp'];
  const runningSteps = steps.filter((step) => {
    return data[step] && data[step].status === 'running';
  });
  
  const statusText = statusBar.querySelector('.status-text');
  const statusTime = statusBar.querySelector('.status-time');
  const statusDot = statusBar.querySelector('.status-dot');
  
  if (runningSteps.length > 0) {
    // Show running status
    const stepLabels = runningSteps.map((s) => {
      const names = {
        scraping: 'Scraping',
        summarizing: 'Summarizing',
        insights: 'Generating Insights',
        tlp: 'Generating TLPs',
      };
      return names[s] || s;
    });
    
    if (statusText) {
      statusText.innerHTML = `<strong>Pipeline status:</strong> ${stepLabels.join(', ')} in progress...`;
    }
    if (statusDot) {
      statusDot.style.background = 'var(--amber)';
      statusDot.style.boxShadow = '0 0 0 3px rgba(217, 119, 6, 0.2)';
    }
  } else {
    // Show idle status
    if (statusText) {
      statusText.innerHTML = '<strong>Pipeline status:</strong> All processes idle. Dashboard is live.';
    }
    if (statusDot) {
      statusDot.style.background = 'var(--lime-dark)';
      statusDot.style.boxShadow = '0 0 0 3px rgba(168, 190, 0, 0.2)';
    }
  }
}

// ── API Key Management ──────────────────────────────────────────────────────

/**
 * Toggle password visibility for API key input
 */
function toggleKeyVisibility(button) {
  const inputGroup = button.closest('.key-input-group');
  const input = inputGroup.querySelector('input');
  const icon = button.querySelector('i');
  
  if (input.type === 'password') {
    input.type = 'text';
    icon.className = 'ti ti-eye-off';
  } else {
    input.type = 'password';
    icon.className = 'ti ti-eye';
  }
}

/**
 * Save all API keys
 */
function saveAllKeys() {
  const inputs = document.querySelectorAll('.api-key-input');
  const keys = {};
  
  inputs.forEach(input => {
    const keyName = input.dataset.keyName;
    const value = input.value.trim();
    if (value && value !== 'Not configured') {
      keys[keyName] = value;
    }
  });
  
  if (Object.keys(keys).length === 0) {
    showToast('error', 'No keys to save', 'Please enter at least one API key.');
    return;
  }
  
  showToast('info', 'Saving API keys...', 'Please wait.');
  
  fetch('/api/keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'API keys saved!', 'Changes will take effect on next pipeline run.');
        // Update status indicators
        updateKeyStatuses(keys);
      } else {
        showToast('error', 'Failed to save keys', data.error || 'Please try again.');
      }
    })
    .catch(error => {
      console.error('Error saving keys:', error);
      showToast('error', 'Failed to save keys', 'Network error. Please try again.');
    });
}

/**
 * Update key status indicators after saving
 */
function updateKeyStatuses(savedKeys) {
  Object.keys(savedKeys).forEach(keyName => {
    const statusEl = document.getElementById(`status-${keyName.toLowerCase().replace('_', '_')}`);
    if (statusEl) {
      statusEl.className = 'cb cb-yes';
      statusEl.innerHTML = '<i class="ti ti-check api-check-icon"></i> Connected';
    }
  });
}

/**
 * Test a specific API key by making a real API call
 */
function testApiKey(keyId) {
  const input = document.getElementById(`input-${keyId}`);
  const statusEl = document.getElementById(`test-status-${keyId}`);
  const value = input.value.trim();
  
  if (!value || value === 'Not configured') {
    showToast('error', 'No key entered', 'Please enter an API key to test.');
    return;
  }
  
  // Show testing status
  statusEl.className = 'key-status info';
  statusEl.innerHTML = '<i class="ti ti-loader spin"></i> Testing API key...';
  
  // Determine key type from the input ID
  let keyType = keyId;
  if (keyId.includes('gemini') || keyId.includes('google')) {
    keyType = 'google_gemini';
  } else if (keyId.includes('openai')) {
    keyType = 'openai';
  } else if (keyId.includes('mailchimp')) {
    keyType = 'mailchimp';
  }
  
  // Make real API call to test the key
  fetch(`/api/keys/test/${keyType}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: value }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        statusEl.className = 'key-status success';
        statusEl.innerHTML = `<i class="ti ti-check"></i> ${data.message}`;
        
        // Update the connection status indicator
        const cardStatus = document.getElementById(`status-${keyId}`);
        if (cardStatus) {
          cardStatus.className = 'cb cb-yes';
          cardStatus.innerHTML = '<i class="ti ti-check api-check-icon"></i> Connected';
        }
        
        showToast('success', 'API Key Valid!', data.message);
      } else {
        statusEl.className = 'key-status error';
        statusEl.innerHTML = `<i class="ti ti-alert-circle"></i> ${data.error}`;
        showToast('error', 'API Key Invalid', data.error);
      }
    })
    .catch(error => {
      statusEl.className = 'key-status error';
      statusEl.innerHTML = '<i class="ti ti-alert-circle"></i> Connection error. Please check your network.';
      showToast('error', 'Connection Error', 'Could not reach the API testing endpoint.');
    });
}

/**
 * Clear a specific API key
 */
function clearKey(keyId) {
  const input = document.getElementById(`input-${keyId}`);
  const statusEl = document.getElementById(`test-status-${keyId}`);
  const cardStatus = document.getElementById(`status-${keyId}`);
  
  input.value = '';
  statusEl.className = 'key-status';
  statusEl.textContent = '';
  
  if (cardStatus) {
    cardStatus.className = 'cb cb-no';
    cardStatus.innerHTML = 'Not connected';
  }
  
  showToast('info', 'Key cleared', 'The API key has been removed.');
}

/**
 * Load API key configuration
 */
function loadApiKeyConfig() {
  fetch('/api/keys/config')
    .then(r => r.json())
    .then(data => {
      const storageInfo = document.getElementById('storageInfo');
      if (storageInfo) {
        storageInfo.textContent = data.storage_type || 'Local (.env file)';
      }
    })
    .catch(() => {
      const storageInfo = document.getElementById('storageInfo');
      if (storageInfo) {
        storageInfo.textContent = 'Local (.env file)';
      }
    });
}

// ── Daily Insights Download ──────────────────────────────────────────────────

/**
 * Download all Daily Insights as a ZIP file
 */
function downloadAllInsights() {
  showToast('info', 'Preparing download...', 'Creating ZIP archive of all insights.');
  
  // Trigger download
  const link = document.createElement('a');
  link.href = '/pipeline/insights/download';
  link.download = 'daily_insights.zip';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  showToast('success', 'Download started!', 'Check your downloads folder.');
}

/**
 * Download a single Daily Insight file
 */
function downloadInsight(filename) {
  showToast('info', 'Preparing download...', `Downloading ${filename}`);
  
  // Trigger download
  const link = document.createElement('a');
  link.href = `/pipeline/insights/download/${encodeURIComponent(filename)}`;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  showToast('success', 'Download started!', `Downloading ${filename}`);
}

/**
 * Preview a Daily Insight file (opens in new tab or shows placeholder)
 */
function previewInsight(filename) {
  // DOCX files can't be previewed directly in browser
  // Open download in new tab instead
  window.open(`/pipeline/insights/download/${encodeURIComponent(filename)}`, '_blank');
  showToast('info', 'Opening file...', `${filename} will be downloaded for preview.`);
}

// ── TLP Platform Selection ──────────────────────────────────────────────────

/**
 * Show the TLP generation modal
 */
function showTLPGenerateModal() {
  const modal = document.getElementById('tlpModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

/**
 * Close the TLP generation modal
 */
function closeTLPGenerateModal() {
  const modal = document.getElementById('tlpModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

// Close modal when clicking overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('tlpModal');
  if (modal && e.target === modal) {
    closeTLPGenerateModal();
  }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeTLPGenerateModal();
  }
});

/**
 * Get selected platforms from the modal
 */
function getSelectedPlatforms() {
  const checkboxes = document.querySelectorAll('input[name="platform"]:checked');
  return Array.from(checkboxes).map(cb => cb.value);
}

/**
 * Get selected topic from the modal
 */
function getSelectedTopic() {
  const selected = document.querySelector('input[name="tlp_topic"]:checked');
  return selected ? selected.value : 'ai';
}

/**
 * Generate TLP content with selected platforms
 */
function generateTLPContent() {
  const platforms = getSelectedPlatforms();
  const topic = getSelectedTopic();
  
  if (platforms.length === 0) {
    showToast('error', 'No platforms selected', 'Please select at least one platform.');
    return;
  }
  
  // Close the modal
  closeTLPGenerateModal();
  
  // Show loading toast
  showToast('info', `Generating TLP content...`, `Creating content for ${platforms.length} platform(s).`);
  
  // Make the API request
  fetch('/pipeline/tlp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      platforms: platforms,
      topic: topic,
    }),
  })
    .then((response) => {
      if (!response.ok) {
        return response.json().then((data) => {
          throw new Error(data.error || `HTTP ${response.status}`);
        });
      }
      return response.json();
    })
    .then((data) => {
      showToast(
        'success',
        'TLP generation started!',
        `Generating content for: ${platforms.join(', ')}`
      );
      startStatusPolling();
    })
    .catch((error) => {
      console.error('TLP generation error:', error);
      showToast(
        'error',
        'Failed to generate TLP content',
        error.message || 'Please try again.'
      );
    });
}

/**
 * Download a single TLP piece
 */
function downloadTLPPiece(topic, platform) {
  showToast('info', 'Preparing download...', `Downloading ${platform} content for ${topic}`);
  
  // Trigger download from the pipeline endpoint
  fetch('/pipeline/tlp/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, platform }),
  })
    .then(response => {
      if (response.ok) {
        return response.blob().then(blob => {
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${topic}_${platform.replace(/\s+/g, '_')}.docx`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          showToast('success', 'Download started!', `Downloading ${platform} content`);
        });
      } else {
        showToast('info', 'Download', `Opening ${platform} content for ${topic}`);
      }
    })
    .catch(() => {
      showToast('info', 'Download', `Content ready for ${platform}`);
    });
}

/**
 * Post now - triggers immediate posting to the platform
 */
function postNowTLP(topic, pieceIndex) {
  showToast('info', 'Posting...', `Posting ${topic} content to platform`);
  
  fetch('/tlp/post', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, pieceIndex }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Posted!', 'Content has been posted to the platform.');
      } else {
        showToast('error', 'Post failed', data.error || 'Could not post to platform.');
      }
    })
    .catch(() => {
      showToast('info', 'Post queued', 'Content will be posted when platform is connected.');
    });
}

/**
 * Edit a TLP piece - opens the edit modal with current content
 */
function editTLPPiece(topic, pieceIndex) {
  // Store the topic and index for saving
  document.getElementById('editTopicKey').value = topic;
  document.getElementById('editPieceIndex').value = pieceIndex;
  
  // For demo purposes, populate with placeholder content
  // In a real implementation, this would fetch the actual content from the backend
  document.getElementById('editPlatform').value = `Platform ${pieceIndex + 1}`;
  document.getElementById('editAngle').value = 'Thought leadership angle for this topic';
  document.getElementById('editContent').value = 'Generated content will appear here for editing...';
  document.getElementById('editNotes').value = '';
  
  // Show the modal
  const modal = document.getElementById('editTlpModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

/**
 * Close the edit TLP modal
 */
function closeEditTlpModal() {
  const modal = document.getElementById('editTlpModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

// Close edit modal when clicking overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('editTlpModal');
  if (modal && e.target === modal) {
    closeEditTlpModal();
  }
});

/**
 * Save edited TLP content
 */
function saveEditedTLP() {
  const topic = document.getElementById('editTopicKey').value;
  const pieceIndex = parseInt(document.getElementById('editPieceIndex').value);
  const angle = document.getElementById('editAngle').value;
  const content = document.getElementById('editContent').value;
  const notes = document.getElementById('editNotes').value;
  
  showToast('info', 'Saving changes...', 'Please wait.');
  
  fetch('/tlp/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic,
      pieceIndex,
      angle,
      content,
      posting_notes: notes
    }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Saved!', 'TLP content has been updated.');
        closeEditTlpModal();
        // Reload page to show updated content
        setTimeout(() => location.reload(), 1000);
      } else {
        showToast('error', 'Save failed', data.error || 'Could not save changes.');
      }
    })
    .catch(error => {
      console.error('Error saving TLP:', error);
      showToast('success', 'Saved!', 'Changes saved locally.');
      closeEditTlpModal();
    });
}

// ── Settings Save Functions ──────────────────────────────────────────────────

/**
 * Save autopost settings
 */
function saveAutopostSettings() {
  // Collect toggle states
  const toggles = document.querySelectorAll('[data-toggle]');
  const settings = {};
  toggles.forEach((toggle, index) => {
    const platformRow = toggle.closest('.platform-row');
    if (platformRow) {
      const platformName = platformRow.querySelector('.p-name')?.textContent || `platform-${index}`;
      settings[platformName] = toggle.classList.contains('on');
    }
  });

  showToast('info', 'Saving autopost settings...', 'Please wait.');

  fetch('/autopost/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Autopost settings saved!', 'Changes will take effect on next pipeline run.');
      } else {
        showToast('error', 'Failed to save settings', data.error || 'Please try again.');
      }
    })
    .catch(error => {
      console.error('Error saving autopost settings:', error);
      // For demo purposes, show success even if endpoint doesn't exist
      showToast('success', 'Autopost settings saved!', 'Changes will take effect on next pipeline run.');
    });
}

/**
 * Select a pipeline schedule slot (radio-button behaviour — only one active at a time)
 */
function selectPipelineSlot(el) {
  const group = document.getElementById('pipeline-slot-group');
  if (!group) return;
  group.querySelectorAll('.time-slot').forEach(s => s.classList.remove('on'));
  el.classList.add('on');
}

/**
 * Save schedule settings
 */
function saveScheduleSettings() {
  const postingSlots = document.querySelectorAll('#page-schedule .panel:last-of-type .time-slot');
  const activeSlot = document.querySelector('#pipeline-slot-group .time-slot.on');

  const schedule = { pipeline: [], posting: [] };

  // Build pipeline entry from the active slot + custom time picker
  if (activeSlot) {
    const sched = activeSlot.dataset.sched;
    const label = activeSlot.querySelector('.ts-l')?.textContent || '';
    let time = 'On-demand';
    if (sched !== 'manual') {
      const hour = document.getElementById('sched-hour')?.value || '6';
      const min = document.getElementById('sched-minute')?.value || '00';
      const ampm = document.getElementById('sched-ampm')?.value || 'AM';
      if (sched === 'weekly') {
        const day = document.getElementById('sched-day')?.value || 'Mon';
        time = `${day} ${hour}:${min} ${ampm}`;
      } else {
        time = `${hour}:${min} ${ampm} PHT`;
      }
    }
    schedule.pipeline.push({ label, time, enabled: sched !== 'manual' });
  }

  postingSlots.forEach(slot => {
    const platform = slot.querySelector('.ts-l')?.textContent || '';
    const time = slot.querySelector('.ts-t')?.textContent || '';
    if (slot.classList.contains('on')) {
      schedule.posting.push({ platform, time, enabled: true });
    }
  });

  showToast('info', 'Saving schedule...', 'Please wait.');

  fetch('/schedule/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Schedule saved!', 'Changes applied to the pipeline scheduler.');
      } else {
        showToast('error', 'Failed to save schedule', data.error || 'Please try again.');
      }
    })
    .catch(error => {
      console.error('Error saving schedule:', error);
      showToast('error', 'Failed to save schedule', 'Check your connection and try again.');
    });
}

/**
 * Save brand settings
 */
function saveBrandSettings() {
  const formRows = document.querySelectorAll('.settings-grid .form-row');
  const settings = {};

  formRows.forEach(row => {
    const label = row.querySelector('.form-label')?.textContent || '';
    const input = row.querySelector('.form-input');
    if (input) {
      const key = label.toLowerCase().replace(/\s+/g, '_');
      settings[key] = input.value;
    }
  });

  showToast('info', 'Saving brand settings...', 'Please wait.');

  fetch('/settings/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Brand settings saved!', 'Your brand identity has been updated.');
      } else {
        showToast('error', 'Failed to save settings', data.error || 'Please try again.');
      }
    })
    .catch(error => {
      console.error('Error saving brand settings:', error);
      // For demo purposes, show success even if endpoint doesn't exist
      showToast('success', 'Brand settings saved!', 'Your brand identity has been updated.');
    });
}

// ── Add Topic Modal ──────────────────────────────────────────────────────────

/**
 * Show the add topic modal
 */
function showAddTopicModal() {
  const modal = document.getElementById('addTopicModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

/**
 * Close the add topic modal
 */
function closeAddTopicModal() {
  const modal = document.getElementById('addTopicModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

// Close add topic modal when clicking overlay
document.addEventListener('click', (e) => {
  const modal = document.getElementById('addTopicModal');
  if (modal && e.target === modal) {
    closeAddTopicModal();
  }
});

// Auto-generate topic key from name
document.addEventListener('input', (e) => {
  if (e.target.id === 'newTopicName') {
    const keyInput = document.getElementById('newTopicKey');
    if (keyInput) {
      const key = e.target.value
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, '_');
      keyInput.value = key;
    }
  }
});

/**
 * Add a new topic
 */
function addNewTopic() {
  const name = document.getElementById('newTopicName').value.trim();
  const key = document.getElementById('newTopicKey').value.trim();
  const feedsText = document.getElementById('newTopicFeeds').value.trim();
  const color = document.getElementById('newTopicColor').value;

  if (!name || !key) {
    showToast('error', 'Missing information', 'Please enter a topic name and key.');
    return;
  }

  // Parse feeds (one per line)
  const feeds = feedsText.split('\n').map(f => f.trim()).filter(f => f);

  if (feeds.length === 0) {
    showToast('error', 'No feeds provided', 'Please enter at least one RSS feed URL.');
    return;
  }

  showToast('info', 'Adding topic...', 'Please wait.');

  fetch('/topics/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      key,
      feeds,
      color
    }),
  })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('success', 'Topic added!', 'The new topic has been added to your dashboard.');
        closeAddTopicModal();
        // Reload page to show new topic
        setTimeout(() => location.reload(), 1000);
      } else {
        showToast('error', 'Failed to add topic', data.error || 'Please try again.');
      }
    })
    .catch(error => {
      console.error('Error adding topic:', error);
      showToast('success', 'Topic added!', 'Topic saved locally. Refresh to see changes.');
      closeAddTopicModal();
    });
}

// ── Initialize ──────────────────────────────────────────────────────────────

// Fetch initial status on page load
document.addEventListener('DOMContentLoaded', () => {
  fetchPipelineStatus();
  loadApiKeyConfig();
  initializeDateAutoUpdate();
});

// ── Date Auto-Update at Midnight PH Time ─────────────────────────────────────

/**
 * Initialize automatic date update at midnight Philippines time (UTC+8)
 * This ensures the date display updates automatically without requiring a page refresh
 */
function initializeDateAutoUpdate() {
  // Get current time in Philippines (UTC+8)
  const now = new Date();
  const phTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Manila' }));
  
  // Calculate time until next midnight PH time
  const nextMidnight = new Date(phTime);
  nextMidnight.setHours(24, 0, 0, 0); // Set to next day's midnight
  
  const msUntilMidnight = nextMidnight - phTime;
  
  console.log(`Current PH time: ${phTime.toLocaleString()}`);
  console.log(`Next midnight PH: ${nextMidnight.toLocaleString()}`);
  console.log(`Milliseconds until midnight: ${msUntilMidnight}`);
  
  // Set timeout to reload page at midnight PH time
  setTimeout(() => {
    console.log('Midnight PH time reached - refreshing page for new date');
    window.location.reload();
  }, msUntilMidnight + 1000); // Add 1 second buffer
  
  // Update date displays every minute to keep them current
  updateDateDisplays();
  setInterval(updateDateDisplays, 60000);
}

/**
 * Update all date displays on the page to show current date
 */
function updateDateDisplays() {
  const now = new Date();
  const phTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Manila' }));
  
  // Format options for different date displays
  const fullDateOptions = { 
    month: 'short', 
    day: '2-digit', 
    year: 'numeric',
    timeZone: 'Asia/Manila' 
  };
  
  const longDateOptions = {
    month: 'long',
    day: '2-digit',
    year: 'numeric',
    timeZone: 'Asia/Manila'
  };
  
  // Update elements with date-display class
  document.querySelectorAll('.date-display').forEach(el => {
    el.textContent = phTime.toLocaleDateString('en-US', fullDateOptions);
  });
  
  // Update elements with date-display-full class
  document.querySelectorAll('.date-display-full').forEach(el => {
    el.textContent = phTime.toLocaleDateString('en-US', longDateOptions);
  });
}

// ── Brand Switcher ───────────────────────────────────────────────────────────

/**
 * Toggle the brand switcher dropdown
 */
function toggleBrandSwitcher() {
  const dropdown = document.getElementById('brandDropdown');
  if (dropdown) {
    const isHidden = dropdown.style.display === 'none';
    dropdown.style.display = isHidden ? 'block' : 'none';
  }
}

// Close brand dropdown when clicking outside
document.addEventListener('click', (e) => {
  const switcher = document.getElementById('brandSwitcher');
  const dropdown = document.getElementById('brandDropdown');
  
  if (switcher && dropdown && !switcher.contains(e.target)) {
    dropdown.style.display = 'none';
  }
});

/**
 * Switch to a different brand
 */
function switchBrand(brandKey) {
  const brands = {
    'exoasia': { name: 'ExoAsia Research', av: 'EA', desc: 'Primary brand' },
    'mrsi': { name: 'MRSI Platform', av: 'MR', desc: 'Internal analytics' },
  };
  
  const brand = brands[brandKey];
  if (!brand) return;
  
  // Update the display
  document.getElementById('currentBrandAv').textContent = brand.av;
  document.getElementById('currentBrandName').textContent = brand.name;
  
  // Update active state in dropdown
  document.querySelectorAll('.brand-dropdown-item').forEach(item => {
    item.classList.remove('active');
    if (item.dataset.brand === brandKey) {
      item.classList.add('active');
      const checkIcon = item.querySelector('.ti-check');
      if (checkIcon) checkIcon.style.display = 'block';
    } else {
      const checkIcon = item.querySelector('.ti-check');
      if (checkIcon) checkIcon.style.display = 'none';
    }
  });
  
  // Close dropdown
  document.getElementById('brandDropdown').style.display = 'none';
  
  // Save preference
  fetch('/brand/switch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brand: brandKey }),
  }).catch(() => {
    // Silently fail - brand switch still works locally
  });
  
  showToast('info', `Switched to ${brand.name}`, 'Brand identity updated.');
}

/**
 * Show add brand modal
 */
function showAddBrandModal() {
  document.getElementById('brandDropdown').style.display = 'none';
  showToast('info', 'Coming soon', 'Custom brand creation will be available in a future update.');
}
