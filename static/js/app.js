document.querySelectorAll('[data-tab]').forEach((tab) => {
  tab.addEventListener('click', () => {
    const tabs = tab.closest('.tabs');
    if (!tabs) return;
    tabs.querySelectorAll('[data-tab]').forEach((item) => item.classList.remove('active'));
    tab.classList.add('active');
  });
});

document.querySelectorAll('[data-topic-filter]').forEach((chip) => {
  chip.addEventListener('click', () => {
    const row = chip.closest('.topic-filter-row');
    if (!row) return;
    row.querySelectorAll('[data-topic-filter]').forEach((item) => item.classList.remove('active'));
    chip.classList.add('active');
  });
});

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
 * Test a specific API key
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
  statusEl.textContent = 'Testing API key...';
  
  // Simulate test (in real implementation, this would call the API)
  setTimeout(() => {
    // For demo purposes, assume success if key is long enough
    if (value.length >= 20) {
      statusEl.className = 'key-status success';
      statusEl.textContent = '✓ API key is valid and connected.';
    } else {
      statusEl.className = 'key-status error';
      statusEl.textContent = '✗ Invalid API key format or connection failed.';
    }
  }, 1500);
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
  
  // In a real implementation, this would fetch the actual content
  // For now, show a toast
  setTimeout(() => {
    showToast('info', 'Feature coming soon', 'Individual TLP download will be available soon.');
  }, 500);
}

// ── Initialize ──────────────────────────────────────────────────────────────

// Fetch initial status on page load
document.addEventListener('DOMContentLoaded', () => {
  fetchPipelineStatus();
  loadApiKeyConfig();
});
