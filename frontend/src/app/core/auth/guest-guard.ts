import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from './auth';

export const guestGuard: CanActivateFn = (route, state) => {

  const auth = inject(Auth)
  const router = inject(Router)

  if (auth.getToken()) {
    router.navigate(["/dashboard"])
    return false
  }
  return true;
};
