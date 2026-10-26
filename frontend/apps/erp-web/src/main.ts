import { bootstrapApplication } from '@angular/platform-browser';
import { loadAppConfig } from '@trishul/core-config';
import { App } from './app/app';
import { createAppConfig } from './app/app.config';

loadAppConfig()
  .then((config) => bootstrapApplication(App, createAppConfig(config)))
  .catch((err) => {
    console.error(err);
    document.body.textContent =
      'Trishul ERP could not start. Please reload the page or contact support.';
  });
