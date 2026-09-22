/**
 * Component tests for PersonFormFields' auto-guess-Sex-from-First-Name
 * behavior: blurring the First Name field fills in a confidently-guessed
 * Sex, but only while Sex is still at its default ('UNKNOWN') — a value the
 * user picked themselves is never overwritten.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PersonFormFields } from '@pages/FamilyTreePage';
import { guessSexFromFirstName } from '@shared/guessSexFromName';
import '../../i18n';

interface PersonFields {
  givenName: string;
  surname: string;
  sex: string;
  isLiving: boolean;
  birthDate: string;
  deathDate: string;
  birthYear: string;
  deathYear: string;
  bornCity: string;
  bornCountry: string;
  diedCity: string;
  diedCountry: string;
  notes: string;
}

const EMPTY_FIELDS: PersonFields = {
  givenName: '', surname: '', sex: 'UNKNOWN', isLiving: true,
  birthDate: '', deathDate: '', birthYear: '', deathYear: '',
  bornCity: '', bornCountry: '', diedCity: '', diedCountry: '',
  notes: '',
};

function Harness({ initial }: { initial: PersonFields }) {
  const [values, setValues] = React.useState(initial);
  return (
    <>
      <PersonFormFields values={values} onChange={setValues} />
      <output data-testid="sex-value">{values.sex}</output>
    </>
  );
}

describe('PersonFormFields sex auto-guess on First Name blur', () => {
  test('fills in a confident guess when Sex is still UNKNOWN', async () => {
    const user = userEvent.setup();
    render(<Harness initial={EMPTY_FIELDS} />);

    await user.type(screen.getByPlaceholderText('Given name'), 'Emma');
    await user.tab();

    await waitFor(() => {
      expect(screen.getByTestId('sex-value')).toHaveTextContent('FEMALE');
    });
  });

  test('does not overwrite a Sex the user already picked', async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ ...EMPTY_FIELDS, sex: 'MALE' }} />);

    await user.type(screen.getByPlaceholderText('Given name'), 'Emma');
    await user.tab();
    await guessSexFromFirstName('Emma'); // let the blur handler's own lookup settle

    expect(screen.getByTestId('sex-value')).toHaveTextContent('MALE');
  });

  test('leaves Sex unset when the name has no confident guess', async () => {
    const user = userEvent.setup();
    render(<Harness initial={EMPTY_FIELDS} />);

    await user.type(screen.getByPlaceholderText('Given name'), 'Jordan');
    await user.tab();
    await guessSexFromFirstName('Jordan'); // let the blur handler's own lookup settle

    expect(screen.getByTestId('sex-value')).toHaveTextContent('UNKNOWN');
  });
});
