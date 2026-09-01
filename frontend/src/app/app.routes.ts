import { Routes } from '@angular/router';
import { Login } from './features/auth/login/login';
import { Register } from './features/auth/register/register';
import { Dashboard } from './features/dashboard/dashboard';
import { SimulationConfig } from './features/simulation-config/simulation-config';
import { authGuard } from './core/auth-guard';
import { guestGuard } from './core/guest-guard';
import { RiskConfig } from './features/risk-config/risk-config';
import { ConfirmConfig } from './features/confirm-config/confirm-config';
import { SimulationStatus } from './features/simulation-status/simulation-status';

export const routes: Routes = [
    { path: '', component: Login, canActivate: [guestGuard] },
    { path: 'register', component: Register, canActivate: [guestGuard] },
    { path: 'dashboard', component: Dashboard, canActivate: [authGuard] },
    { path: 'simulation-config', component: SimulationConfig, canActivate: [authGuard]},
    { path: 'risk-config/:configurationId', component: RiskConfig, canActivate: [authGuard] },
    { path: 'confirm-config/:configurationId', component: ConfirmConfig, canActivate: [authGuard] },
    { path: 'simulation-status/:simulationId', component: SimulationStatus, canActivate: [authGuard] }
];
