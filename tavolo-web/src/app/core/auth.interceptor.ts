import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { CredService } from './cred.service';

/** Aggiunge le credenziali (header X-Client/X-Secret) a tutte le chiamate POST verso /api. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const c = inject(CredService).cred();
  if (!c || !req.url.startsWith('/api/') || req.method !== 'POST') return next(req);
  return next(req.clone({ setHeaders: { 'X-Client': c.id, 'X-Secret': c.secret } }));
};
