import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import type { WidgetConfig } from './types';
// @ts-ignore — Vite inlines this as a string via ?inline
import styles from './index.css?inline';

/**
 * AanandiAgentElement — Custom Element that mounts the React widget
 * into an isolated Shadow DOM so no host styles bleed through.
 */
class AanandiAgentElement extends HTMLElement {
  private _root: ReactDOM.Root | null = null;
  private _shadowRoot: ShadowRoot;

  constructor() {
    super();
    // Closed shadow root: host page JS cannot access internals
    this._shadowRoot = this.attachShadow({ mode: 'open' });
  }

  static get observedAttributes() {
    return ['api-base', 'theme'];
  }

  connectedCallback() {
    this._mount();
  }

  disconnectedCallback() {
    this._root?.unmount();
    this._root = null;
  }

  attributeChangedCallback() {
    // Re-mount with updated config when attrs change
    if (this._root) {
      this._root.unmount();
      this._mount();
    }
  }

  private _mount() {
    // Inject styles into Shadow DOM
    const styleEl = document.createElement('style');
    styleEl.textContent = styles;

    // Mount point
    const container = document.createElement('div');
    container.id = 'aanandi-root';

    this._shadowRoot.innerHTML = '';
    this._shadowRoot.appendChild(styleEl);
    this._shadowRoot.appendChild(container);

    const defaultBase = typeof window !== 'undefined' && window.location.origin && !window.location.origin.startsWith('file:')
      ? window.location.origin
      : 'http://localhost:8000';

    const config: WidgetConfig = {
      apiBase: this.getAttribute('api-base') || defaultBase,
      theme: (this.getAttribute('theme') as 'dark' | 'light') || 'dark',
    };

    this._root = ReactDOM.createRoot(container);
    this._root.render(
      <React.StrictMode>
        <App config={config} />
      </React.StrictMode>,
    );
  }
}

// Register only once
if (!customElements.get('aanandi-agent')) {
  customElements.define('aanandi-agent', AanandiAgentElement);
}

export {};
