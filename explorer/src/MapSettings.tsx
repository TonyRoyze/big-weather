import {useEffect, useRef, type ReactNode} from 'react';
import {X} from 'lucide-react';

export function MapSettings({open, onClose, children}: {open: boolean; onClose: () => void; children: ReactNode}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current!;
    if (!open) return;
    element.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {element.close(); document.body.style.overflow = previousOverflow;};
  }, [open]);
  return <dialog ref={dialog} className="map-settings" aria-labelledby="map-settings-title"
    onCancel={e => {e.preventDefault(); onClose();}}
    onClick={e => {if (e.target === e.currentTarget) {
      const bounds = e.currentTarget.getBoundingClientRect();
      if (e.clientX < bounds.left || e.clientX > bounds.right || e.clientY < bounds.top || e.clientY > bounds.bottom) onClose();
    }}}>
    <div className="modal-heading"><h2 id="map-settings-title">Map settings</h2><button type="button" className="icon-button" aria-label="Close map settings" onClick={onClose}><X size={20}/></button></div>
    {children}
    <button type="button" className="primary-button modal-done" onClick={onClose}>Done</button>
  </dialog>;
}
