import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrolling. The lesson page scrolls to the top, so give it a harmless version.
import { vi } from "vitest";
window.scrollTo = vi.fn();
