import * as bcrypt from 'bcryptjs';
export const hashPassword = async (password) => {
    const saltRounds = 10;
    return bcrypt.hash(password, saltRounds);
};
export const verifyPassword = async (password, hash) => {
    return bcrypt.compare(password, hash);
};
