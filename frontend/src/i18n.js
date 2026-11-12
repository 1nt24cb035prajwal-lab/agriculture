// Navigation/labels only. Add more keys/languages here; unknown keys fall back to English.
export const LANGS = { en: 'English', kn: 'ಕನ್ನಡ', hi: 'हिन्दी', ta: 'தமிழ்', te: 'తెలుగు', mr: 'मराठी' }
const T = {
  en: { dashboard: 'Dashboard', land: 'Crop & Land', recommend: 'Crop Recommendation', disease: 'Disease Detection', yield: 'Yield Prediction', weather: 'Weather', satellite: 'Satellite', history: 'Activity History', reports: 'Reports', profile: 'Profile', welcome: 'Welcome', logout: 'Logout' },
  kn: { dashboard: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್', land: 'ಬೆಳೆ ಮತ್ತು ಭೂಮಿ', recommend: 'ಬೆಳೆ ಶಿಫಾರಸು', disease: 'ರೋಗ ಪತ್ತೆ', yield: 'ಇಳುವರಿ ಅಂದಾಜು', weather: 'ಹವಾಮಾನ', satellite: 'ಉಪಗ್ರಹ', history: 'ಚಟುವಟಿಕೆ ಇತಿಹಾಸ', reports: 'ವರದಿಗಳು', profile: 'ಪ್ರೊಫೈಲ್', welcome: 'ಸ್ವಾಗತ', logout: 'ಲಾಗ್ ಔಟ್' },
  hi: { dashboard: 'डैशबोर्ड', land: 'फसल और भूमि', recommend: 'फसल सुझाव', disease: 'रोग पहचान', yield: 'उपज अनुमान', weather: 'मौसम', satellite: 'उपग्रह', history: 'गतिविधि इतिहास', reports: 'रिपोर्ट', profile: 'प्रोफ़ाइल', welcome: 'स्वागत है', logout: 'लॉग आउट' },
}
export const tr = (lang, k) => (T[lang] && T[lang][k]) || T.en[k] || k
