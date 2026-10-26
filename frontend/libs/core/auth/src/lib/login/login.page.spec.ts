import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { AuthError, SignInStep } from '../auth-session';
import { AuthService } from '../auth.service';
import { LoginPage, safeReturnUrl } from './login.page';

class FakeAuthService {
  usesPassword = true;
  signIn = vi.fn<(u: string, p: string) => Promise<SignInStep>>();
  completeNewPassword = vi.fn<(p: string) => Promise<SignInStep>>();
  confirmMfaCode = vi.fn<(c: string) => Promise<SignInStep>>();
  sendPasswordResetCode = vi.fn<(u: string) => Promise<string>>();
  resetPassword = vi.fn<(u: string, c: string, p: string) => Promise<void>>();
}

const settle = () => new Promise((resolve) => setTimeout(resolve));

describe('LoginPage', () => {
  let fixture: ComponentFixture<LoginPage>;
  let auth: FakeAuthService;
  let navigate: ReturnType<typeof vi.fn>;

  async function render(
    usesPassword = true,
    returnUrl?: string,
  ): Promise<void> {
    auth = new FakeAuthService();
    auth.usesPassword = usesPassword;
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [provideRouter([]), { provide: AuthService, useValue: auth }],
    });
    navigate = vi.fn().mockResolvedValue(true);
    TestBed.inject(Router).navigateByUrl = navigate;
    fixture = TestBed.createComponent(LoginPage);
    if (returnUrl) fixture.componentRef.setInput('returnUrl', returnUrl);
    await fixture.whenStable();
  }

  const page = () => fixture.nativeElement as HTMLElement;
  const text = () => page().textContent ?? '';

  function type(control: string, value: string): void {
    const input = page().querySelector<HTMLInputElement>(
      `input[formcontrolname="${control}"]`,
    );
    if (!input) throw new Error(`no input ${control}`);
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  async function submit(): Promise<void> {
    page().querySelector<HTMLButtonElement>('button[type="submit"]')?.click();
    await settle();
    await fixture.whenStable();
  }

  it('signs in and returns to the page the user came from', async () => {
    await render(true, '/service/calls');
    auth.signIn.mockResolvedValue('done');
    type('username', 'team.lead');
    type('password', 'correct horse battery');
    await submit();
    expect(auth.signIn).toHaveBeenCalledWith(
      'team.lead',
      'correct horse battery',
    );
    expect(navigate).toHaveBeenCalledWith('/service/calls');
  });

  it('requires username and password before calling Cognito', async () => {
    await render();
    await submit();
    expect(auth.signIn).not.toHaveBeenCalled();
    expect(text()).toContain('Enter your email.');
    expect(text()).toContain('Enter your password.');
  });

  it('shows the error message and stays on the page', async () => {
    await render();
    auth.signIn.mockRejectedValue(
      new AuthError('Incorrect username or password.'),
    );
    type('username', 'team.lead');
    type('password', 'wrong');
    await submit();
    expect(page().querySelector('[role="alert"]')?.textContent).toContain(
      'Incorrect username or password.',
    );
    expect(navigate).not.toHaveBeenCalled();
  });

  it('asks for a new password after a temporary one, then signs in', async () => {
    await render();
    auth.signIn.mockResolvedValue('new-password');
    auth.completeNewPassword.mockResolvedValue('done');
    type('username', 'new.joiner');
    type('password', 'Temp#12345678');
    await submit();
    expect(text()).toContain('Choose a new password');

    type('password', 'a-much-better-passphrase');
    type('confirm', 'different-passphrase-1');
    await submit();
    expect(auth.completeNewPassword).not.toHaveBeenCalled();
    expect(text()).toContain("The passwords don't match.");

    type('confirm', 'a-much-better-passphrase');
    await submit();
    expect(auth.completeNewPassword).toHaveBeenCalledWith(
      'a-much-better-passphrase',
    );
    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('asks for the MFA code when Cognito requires one', async () => {
    await render();
    auth.signIn.mockResolvedValue('mfa-code');
    auth.confirmMfaCode.mockResolvedValue('done');
    type('username', 'accounts.head');
    type('password', 'correct horse battery');
    await submit();
    expect(text()).toContain('Enter your code');

    type('code', '123456');
    await submit();
    expect(auth.confirmMfaCode).toHaveBeenCalledWith('123456');
    expect(navigate).toHaveBeenCalled();
  });

  it('resets a forgotten password and returns to sign in', async () => {
    await render();
    page().querySelector<HTMLButtonElement>('button.link')?.click();
    await fixture.whenStable();
    auth.sendPasswordResetCode.mockResolvedValue('r***@trishul.example');
    auth.resetPassword.mockResolvedValue();
    type('username', 'team.lead');
    await submit();
    expect(text()).toContain('r***@trishul.example');

    type('code', '654321');
    type('password', 'a-much-better-passphrase');
    type('confirm', 'a-much-better-passphrase');
    await submit();
    expect(auth.resetPassword).toHaveBeenCalledWith(
      'team.lead',
      '654321',
      'a-much-better-passphrase',
    );
    expect(text()).toContain('Password changed.');
    expect(text()).toContain('Sign in');
  });

  it('development sign-in needs only a username', async () => {
    await render(false);
    expect(
      page().querySelector('input[formcontrolname="password"]'),
    ).toBeNull();
    expect(text()).toContain('Development sign-in');
    auth.signIn.mockResolvedValue('done');
    type('username', 'demo.admin');
    await submit();
    expect(auth.signIn).toHaveBeenCalledWith('demo.admin', '');
  });
});

describe('safeReturnUrl', () => {
  it.each([
    ['/service/calls', '/service/calls'],
    [undefined, '/'],
    ['https://evil.example', '/'],
    ['//evil.example', '/'],
    ['/\\evil.example', '/'],
    ['/login?returnUrl=/x', '/'],
  ])('%s -> %s', (input, expected) => {
    expect(safeReturnUrl(input)).toBe(expected);
  });
});
