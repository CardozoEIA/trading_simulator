import { Routes } from '@angular/router';
import { Login } from './features/auth/login/login';
import { Register } from './features/auth/register/register';
import { Dashboard } from './features/dashboard/dashboard';
import { SimulationConfig } from './features/simulation/simulation-config/simulation-config';
import { authGuard } from '@core/auth/auth-guard';
import { guestGuard } from '@core/auth/guest-guard';
import { RiskConfig } from './features/simulation/risk-config/risk-config';
import { ConfirmConfig } from './features/simulation/confirm-config/confirm-config';
import { SimulationStatus } from './features/simulation/simulation-status/simulation-status';
import { SimulationDecisions } from './features/simulation/simulation-decisions/simulation-decisions';
import { SimulationHistory } from './features/simulation/simulation-history/simulation-history';
import { Knowledge } from './features/knowledge/knowledge';
import { SimulationCompare } from './features/simulation/simulation-compare/simulation-compare';
import { CustomStrategies } from './features/simulation/custom-strategies/custom-strategies';


export const routes: Routes = [
    { path: '', component: Login, canActivate: [guestGuard] },
    { path: 'register', component: Register, canActivate: [guestGuard] },
    { path: 'dashboard', component: Dashboard, canActivate: [authGuard] },
    { path: 'simulation-config', component: SimulationConfig, canActivate: [authGuard]},
    { path: 'risk-config/:configurationId', component: RiskConfig, canActivate: [authGuard] },
    { path: 'confirm-config/:configurationId', component: ConfirmConfig, canActivate: [authGuard] },
    { path: 'simulation-status/:simulationId', component: SimulationStatus, canActivate: [authGuard] },
    { path: 'simulation-decisions/:simulationId', component: SimulationDecisions, canActivate: [authGuard] },
    { path: 'history', component: SimulationHistory, canActivate: [authGuard] },
    { path: 'compare', component: SimulationCompare, canActivate: [authGuard] },
    { path: 'custom-strategies', component: CustomStrategies, canActivate: [authGuard] },
    { path: 'knowledge', component: Knowledge, canActivate: [authGuard] },
];
