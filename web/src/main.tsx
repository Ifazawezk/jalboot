import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { loadApi } from './api';
import { App } from './App';
import { readInitialLocale } from './i18n/context';
import './styles/fonts.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/chat.css';
import './styles/desk.css';

const api = await loadApi();
api.setLocale(readInitialLocale());

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App api={api} />
    </StrictMode>,
  );
}
