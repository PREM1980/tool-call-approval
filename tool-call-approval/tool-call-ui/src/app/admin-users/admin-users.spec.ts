import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { AdminUsers } from './admin-users';
import { AdminService, AppUser } from '../services/admin.service';

function makeUser(overrides: Partial<AppUser> = {}): AppUser {
  return {
    id: 'user-1',
    username: 'admin',
    role: 'admin',
    ...overrides,
  };
}

function makeAdminService(initialUsers: AppUser[] = []) {
  return {
    listUsers: jasmine.createSpy('listUsers').and.resolveTo(initialUsers),
    createUser: jasmine
      .createSpy('createUser')
      .and.callFake((username: string, _password: string, role: 'admin' | 'user') =>
        Promise.resolve(makeUser({ id: 'created-user', username, role })),
      ),
    updateUserRole: jasmine
      .createSpy('updateUserRole')
      .and.callFake((id: string, role: 'admin' | 'user') =>
        Promise.resolve(makeUser({ id, username: 'alice', role })),
      ),
  };
}

describe('AdminUsers', () => {
  afterEach(() => TestBed.resetTestingModule());

  async function setup(initialUsers: AppUser[] = []): Promise<{
    fixture: ComponentFixture<AdminUsers>;
    adminService: ReturnType<typeof makeAdminService>;
  }> {
    const adminService = makeAdminService(initialUsers);
    await TestBed.configureTestingModule({
      imports: [AdminUsers],
      providers: [{ provide: AdminService, useValue: adminService }],
    }).compileComponents();

    const fixture = TestBed.createComponent(AdminUsers);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, adminService };
  }

  it('loads and lists existing users', async () => {
    const { fixture, adminService } = await setup([
      makeUser(),
      makeUser({ id: 'user-2', username: 'alice', role: 'user' }),
    ]);

    expect(adminService.listUsers).toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('2 active accounts');
    expect(fixture.nativeElement.textContent).toContain('admin');
    expect(fixture.nativeElement.textContent).toContain('alice');
  });

  it('submits username, password, and role when creating a user', async () => {
    const { fixture, adminService } = await setup();

    setInputValue(fixture, '#newUsername', 'ops-admin');
    setInputValue(fixture, '#newPassword', 'shared-secret');
    setSelectValue(fixture, '#role', 'admin');
    fixture.detectChanges();

    fixture.debugElement.query(By.css('form')).triggerEventHandler('ngSubmit');
    await fixture.whenStable();
    fixture.detectChanges();

    expect(adminService.createUser).toHaveBeenCalledOnceWith(
      'ops-admin',
      'shared-secret',
      'admin',
    );
    expect(fixture.nativeElement.textContent).toContain('ops-admin');
    expect(fixture.nativeElement.textContent).toContain('Created ops-admin');
  });

  it('saves role changes for an existing user', async () => {
    const { fixture, adminService } = await setup([
      makeUser(),
      makeUser({ id: 'user-2', username: 'alice', role: 'user' }),
    ]);

    setSelectValue(fixture, '[data-testid="role-select-user-2"]', 'admin');
    fixture.detectChanges();

    fixture.debugElement
      .query(By.css('[data-testid="save-role-user-2"]'))
      .nativeElement.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(adminService.updateUserRole).toHaveBeenCalledOnceWith('user-2', 'admin');
    expect(fixture.nativeElement.textContent).toContain('Updated alice');
    expect((fixture.nativeElement.querySelector('[data-testid="role-select-user-2"]') as HTMLSelectElement).value)
      .toBe('admin');
  });
});

function setInputValue(
  fixture: ComponentFixture<AdminUsers>,
  selector: string,
  value: string,
): void {
  const input = fixture.nativeElement.querySelector(selector) as HTMLInputElement;
  input.value = value;
  input.dispatchEvent(new Event('input'));
}

function setSelectValue(
  fixture: ComponentFixture<AdminUsers>,
  selector: string,
  value: string,
): void {
  const select = fixture.nativeElement.querySelector(selector) as HTMLSelectElement;
  select.value = value;
  select.dispatchEvent(new Event('change'));
}
