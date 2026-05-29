const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Polyfill Node.js built-ins required by react-native-audio
config.resolver.extraNodeModules = {
  buffer: require.resolve('buffer'),
};

module.exports = config;
