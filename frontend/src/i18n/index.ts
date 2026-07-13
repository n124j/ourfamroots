import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en';
import ne from './locales/ne';

const STORAGE_KEY = 'ourfamroots_language';

function getSavedLanguage(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'en';
  } catch {
    return 'en';
  }
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ne: { translation: ne },
  },
  lng: getSavedLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export function changeLanguage(lng: string) {
  i18n.changeLanguage(lng);
  try {
    localStorage.setItem(STORAGE_KEY, lng);
  } catch {}
}

export function getCurrentLanguage(): string {
  return i18n.language || 'en';
}

// Fixed-English translator — for surfaces (e.g. the public landing page)
// that must always render in English regardless of the user's selected
// app language, signed in or out.
export function getEnglishT() {
  return i18n.getFixedT('en');
}

export default i18n;
