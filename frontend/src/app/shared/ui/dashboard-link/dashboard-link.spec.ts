import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { Component } from '@angular/core';

import { Alert } from '../alert/alert';
import { DashboardLink } from './dashboard-link';

@Component({ template: '' })
class Blank {}

describe('DashboardLink', () => {
  let router: Router;
  let confirmLeave: jasmine.Spy;

  async function setup(url: string) {
    TestBed.configureTestingModule({
      imports: [DashboardLink],
      providers: [
        provideRouter(['', 'register', 'dashboard', 'history', 'risk-config/:id'].map((path) => ({ path, component: Blank }))),
      ],
    });
    router = TestBed.inject(Router);
    confirmLeave = spyOn(TestBed.inject(Alert), 'confirmLeaveWizard').and.resolveTo(true);
    const fixture = TestBed.createComponent(DashboardLink);
    await router.navigateByUrl(url);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('is hidden on login, register and the dashboard itself', async () => {
    for (const url of ['/', '/register', '/dashboard']) {
      const el = await setup(url);
      expect(el.querySelector('button')).toBeNull();
      TestBed.resetTestingModule();
    }
  });

  it('goes straight to the dashboard from a normal page', async () => {
    const el = await setup('/history');
    el.querySelector('button')!.click();
    await new Promise((r) => setTimeout(r));
    expect(router.url).toBe('/dashboard');
    expect(confirmLeave).not.toHaveBeenCalled();
  });

  it('asks before leaving a wizard step and stays if the student declines', async () => {
    const el = await setup('/risk-config/abc');
    confirmLeave.and.resolveTo(false);
    el.querySelector('button')!.click();
    await new Promise((r) => setTimeout(r));
    expect(confirmLeave).toHaveBeenCalled();
    expect(router.url).toBe('/risk-config/abc');
  });
});
