import {
  Link,
} from "@tanstack/react-router"

const DiscordButton = ({ inviteCode }) => {
  const url = `https://discord.gg/${inviteCode}`;

  const buttonStyle = {
    backgroundColor: '#5865F2', // Discord's blurple color
    color: 'white',
    padding: '10px 16px',
    fontSize: '16px',
    fontWeight: '500',
    borderRadius: '3px',
    border: 'none',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
    textDecoration: 'none', // Make sure the Link text is not underlined

    '&:hover': {
      backgroundColor: '#4752c4', // Darker shade on hover
    },
    '&:focus': {
      outline: 'none',
      boxShadow: '0 0 0 2px rgba(88, 101, 242, 0.5)', // Optional focus highlight
    },
  };

  return (
    <Link to={url} style={buttonStyle}>
      Join our Discord
    </Link>
  );
};

export default DiscordButton;