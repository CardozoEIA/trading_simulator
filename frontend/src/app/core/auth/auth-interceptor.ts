import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, EMPTY, throwError } from 'rxjs';

import { Auth } from './auth';

export const authInterceptor: HttpInterceptorFn = (req, next) => {

  const auth = inject(Auth);
  const router = inject(Router);

  const token = auth.getToken();

  const request = token
    ? req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    })
    : req;

  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {

      // Expired or invalid session: go back to the login silently.
      // Only when a token was sent, so a wrong password on the login form still shows its error.
      if (error.status === 401 && token) {
        auth.logout();
        router.navigate(['/']);
        return EMPTY;
      }

      return throwError(() => error);
    })
  );
};