import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

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

      if (error.status === 401) {
        auth.logout();
        router.navigate(['/']);
      }

      return throwError(() => error);
    })
  );
};