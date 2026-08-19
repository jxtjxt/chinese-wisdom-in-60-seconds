import React from 'react';

export const CenteredBlock = ({top, bottom, width, style, children}) => {
  const verticalPosition = top === undefined ? {bottom} : {top};

  return (
    <div
      style={{
        position: 'absolute',
        textAlign: 'center',
        ...verticalPosition,
        ...style,
        left: '50%',
        width,
        transform: 'translateX(-50%)',
      }}
    >
      {children}
    </div>
  );
};
