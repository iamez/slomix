import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// The assertions are correct at 1s in isolation; under the full 19-file
// parallel run a worker can be CPU-starved past the default asyncUtilTimeout,
// which failed different tests on different runs (Home search, Landing dash).
configure({ asyncUtilTimeout: 5000 });
