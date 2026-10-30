import '@testing-library/jest-dom/vitest';

// jsdom does not implement scrolling; navigation calls it after switching views.
window.scrollTo = () => undefined;
