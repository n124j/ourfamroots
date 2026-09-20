import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AiTreeImportPanel } from '@features/admin/aiTreeImport/AiTreeImportPanel';
import { useAiTreeImportJob } from '@features/admin/aiTreeImport/useAiTreeImportJob';
import { post } from '@api/client';

vi.mock('@features/admin/aiTreeImport/useAiTreeImportJob');
vi.mock('@api/client', () => ({ post: vi.fn() }));

describe('AiTreeImportPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the editable draft once the job is ready and finalizes it', async () => {
    (useAiTreeImportJob as any).mockReturnValue({
      status: 'ready',
      jobId: 'job-1',
      draft: {
        persons: [{ id: 'p1', display_given_name: 'Jane', display_surname: 'Doe', sex: 'FEMALE' }],
        family_groups: [],
      },
      photoUrls: {},
      errorMessage: null,
      uploadScreenshot: vi.fn(),
      reset: vi.fn(),
    });
    (post as any).mockResolvedValue({ tree_id: 'tree-1', tree_name: 'From Screenshot' });

    render(<AiTreeImportPanel />);

    expect(screen.getByDisplayValue('Jane')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /create tree/i }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/admin/ai-tree-import/job-1/finalize',
        expect.objectContaining({ persons: expect.arrayContaining([expect.objectContaining({ display_given_name: 'Jane' })]) })
      )
    );
    expect(await screen.findByText(/from screenshot/i)).toBeInTheDocument();
  });

  it('shows the error message when the job fails', () => {
    (useAiTreeImportJob as any).mockReturnValue({
      status: 'error', jobId: null, draft: null, photoUrls: {},
      errorMessage: 'Vision API call failed', uploadScreenshot: vi.fn(), reset: vi.fn(),
    });

    render(<AiTreeImportPanel />);
    expect(screen.getByText('Vision API call failed')).toBeInTheDocument();
  });
});
